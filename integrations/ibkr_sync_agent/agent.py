"""Read-only boundary for a local TWS/IB Gateway integration."""
from abc import ABC, abstractmethod
import hashlib
import os
import requests

class PortfolioProvider(ABC):
    @abstractmethod
    def list_accounts(self): ...
    @abstractmethod
    def get_positions(self, account_id: str): ...
    @abstractmethod
    def get_account_summary(self, account_id: str): ...

class IBKRTWSProvider(PortfolioProvider):
    """Adapter placeholder: local-only TWS implementation belongs here."""
    def __init__(self, host, port, client_id): self.host, self.port, self.client_id = host, port, client_id
    def list_accounts(self): raise NotImplementedError("Install/configure a local TWS adapter")
    def get_positions(self, account_id): raise NotImplementedError
    def get_account_summary(self, account_id): raise NotImplementedError

class IBKRWebAPIProvider(PortfolioProvider):
    def list_accounts(self): raise NotImplementedError
    def get_positions(self, account_id): raise NotImplementedError
    def get_account_summary(self, account_id): raise NotImplementedError

def push_snapshot(snapshot: dict) -> dict:
    url = os.environ["FIELDNOTES_API_URL"].rstrip("/") + "/api/integrations/ibkr/sync"
    response = requests.post(url, json=snapshot, headers={"X-FieldNotes-Sync-Token": os.environ["FIELDNOTES_SYNC_TOKEN"]}, timeout=30)
    response.raise_for_status()
    return response.json()
