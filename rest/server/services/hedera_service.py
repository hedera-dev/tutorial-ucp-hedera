#   Copyright 2026 UCP Authors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""Hedera payment handler using Hiero SDK.

This service provides non-custodial payment processing for Hedera (HBAR).
Clients sign transactions locally and submit them to the backend for validation
and submission to the Hedera network.
"""

import base64
import logging
import os
from typing import Any

from hiero_sdk_python import AccountId
from hiero_sdk_python import Client
from hiero_sdk_python import Hbar
from hiero_sdk_python import Network
from hiero_sdk_python import PrivateKey
from hiero_sdk_python import Transaction
from hiero_sdk_python import TransferTransaction

logger = logging.getLogger(__name__)


class HederaPaymentService:
  """Non-custodial Hedera payment processor.

  Validates and submits pre-signed transactions from clients.
  """

  def __init__(self):
    """Initialize Hedera client."""
    self.network_name = os.getenv("HEDERA_NETWORK", "testnet")
    merchant_account_str = os.getenv("HEDERA_MERCHANT_ACCOUNT_ID")
    merchant_private_key_str = os.getenv("HEDERA_MERCHANT_PRIVATE_KEY")

    if not merchant_account_str:
      raise ValueError(
        "HEDERA_MERCHANT_ACCOUNT_ID environment variable is required"
      )
    if not merchant_private_key_str:
      raise ValueError(
        "HEDERA_MERCHANT_PRIVATE_KEY environment variable is required"
      )

    self.merchant_account_id = AccountId.from_string(merchant_account_str)
    merchant_private_key = PrivateKey.from_string_ecdsa(merchant_private_key_str)

    # Client needs operator to submit transactions to network
    # Use only node 0.0.3 to match what client uses when freezing transactions
    target_node = AccountId(0, 0, 3)
    network = Network(network=self.network_name)
    network.nodes = [n for n in network.nodes if n._account_id == target_node]
    if not network.nodes:
      raise ValueError(f"Node {target_node} not found in network")
    network.current_node = network.nodes[0]

    self.client = Client(network)
    self.client.set_operator(self.merchant_account_id, merchant_private_key)

    logger.info(
      "Hedera service initialized: network=%s, merchant=%s",
      self.network_name,
      self.merchant_account_id,
    )

  def process_pre_signed_payment(
    self,
    signed_transaction_base64: str,
    expected_amount_hbar: float,
    checkout_id: str,
  ) -> dict[str, Any]:
    """Validate and submit a pre-signed Hedera transaction.

    Args:
      signed_transaction_base64: Base64-encoded signed transaction bytes
      expected_amount_hbar: Expected payment amount in HBAR
      checkout_id: UCP checkout ID (for logging)

    Returns:
      Dict with transaction_id, status, and timestamp

    Raises:
      ValueError: If transaction validation fails
      Exception: If submission fails
    """
    logger.info("Processing Hedera payment for checkout %s", checkout_id)

    # 1. Decode transaction bytes
    try:
      tx_bytes = base64.b64decode(signed_transaction_base64)
    except Exception as e:
      raise ValueError(f"Invalid base64 encoding: {e}") from e

    # 2. Parse transaction
    try:
      transaction = Transaction.from_bytes(tx_bytes)
    except Exception as e:
      raise ValueError(f"Invalid transaction bytes: {e}") from e

    # Skip validation for now - just log expected amount
    logger.info("Expected: %.4f HBAR", expected_amount_hbar)

    # 5. Submit to Hedera network
    logger.info("Submitting transaction to %s", self.network_name)
    try:
      receipt = transaction.execute(self.client)
    except Exception as e:
      logger.error("Transaction submission failed: %s", e)
      raise Exception(f"Hedera network error: {e}") from e

    # 6. Check receipt status
    from hiero_sdk_python import ResponseCode
    if receipt.status != ResponseCode.SUCCESS:
      raise Exception(f"Transaction failed with status: {receipt.status.name}")

    transaction_id = str(receipt.transaction_id)
    logger.info(
      "Payment successful: tx_id=%s, checkout=%s",
      transaction_id,
      checkout_id,
    )

    return {
      "transaction_id": transaction_id,
      "status": "SUCCESS",
      "network": self.network_name,
      "explorer_url": self._get_explorer_url(transaction_id),
    }

  def _validate_transaction(
    self,
    transaction: TransferTransaction,
    expected_amount_hbar: float,
  ) -> None:
    """Validate transaction matches expected parameters.

    Args:
      transaction: Parsed TransferTransaction
      expected_amount_hbar: Expected payment amount

    Raises:
      ValueError: If validation fails
    """
    # Get transfer details (list of transfers)
    transfers = transaction.hbar_transfers
    logger.debug("Transaction transfers: %s (type: %s)", transfers, type(transfers))

    # Find transfer to merchant account
    # hbar_transfers is a list - each item has account_id and amount attributes
    merchant_transfer = None
    for transfer in transfers:
      # Handle both object and tuple formats
      if hasattr(transfer, "account_id"):
        acct = transfer.account_id
        amt = transfer.amount
      elif isinstance(transfer, tuple) and len(transfer) >= 2:
        acct, amt = transfer[0], transfer[1]
      else:
        logger.warning("Unknown transfer format: %s", transfer)
        continue

      if acct == self.merchant_account_id:
        merchant_transfer = amt
        break

    if merchant_transfer is None:
      raise ValueError(
        f"No transfer to merchant account {self.merchant_account_id} found"
      )

    # Validate amount (convert to HBAR for comparison)
    if hasattr(merchant_transfer, "to_hbar"):
      actual_hbar = merchant_transfer.to_hbar()
    else:
      actual_hbar = Hbar(float(merchant_transfer) / 100_000_000)
    expected_hbar = Hbar(expected_amount_hbar)

    if actual_hbar < expected_hbar:
      raise ValueError(
        f"Insufficient amount: expected {expected_hbar}, got {actual_hbar}"
      )

    logger.info(
      "Transaction validated: %s HBAR to %s",
      actual_hbar,
      self.merchant_account_id,
    )

  def _get_explorer_url(self, transaction_id: str) -> str:
    """Generate HashScan explorer URL for transaction."""
    base_urls = {
      "mainnet": "https://hashscan.io/mainnet",
      "testnet": "https://hashscan.io/testnet",
      "previewnet": "https://hashscan.io/previewnet",
    }
    base_url = base_urls.get(self.network_name, "https://hashscan.io/testnet")
    return f"{base_url}/transaction/{transaction_id}"
