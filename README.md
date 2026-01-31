<!--
   Copyright 2026 UCP Authors

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
-->

# Universal Commerce Protocol (UCP) Samples

This directory contains sample implementations and client scripts for the
Universal Commerce Protocol (UCP).

## Sample Implementations

### REST (Python) - Start Here

A reference implementation of a UCP Merchant Server using Python and FastAPI.

👉 **[Get Started with the REST Tutorial](rest/README.md)**

- **Server**: Located in `rest/server/`
  - Demonstrates capability discovery, checkout session management, payment
    processing, and order lifecycle.
  - Includes simulation endpoints for testing.

- **Client**: Located in `rest/client/`
  - [Happy Path Script](rest/client/flower_shop/simple_happy_path_client.py) -
    A script demonstrating a full "happy path" user journey (discovery ->
    checkout -> payment).

### A2A (Coming Soon)

A reference implementation using Agent 2 Agent (A2A) protocol.

- Located in `rest/a2a/`
- **Status**: Implementation in progress
