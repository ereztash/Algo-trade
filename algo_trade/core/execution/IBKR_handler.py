import os
from ib_insync import IB, util

class IBKRHandler:
    def __init__(self, host=None, port=None, clientId=None, timeout=None, readonly=False):
        """
        Initialize IBKR Handler with configuration from environment or parameters.

        Args:
            host: TWS/Gateway host (default from DP_BROKER__HOST or 127.0.0.1)
            port: TWS/Gateway port (default from DP_BROKER__PORT or 7497)
            clientId: Client ID (default from DP_IBKR__CLIENT_ID or 1)
            timeout: Connection timeout in seconds (default from DP_IBKR__TIMEOUT or 30)
            readonly: Read-only mode prevents order execution (default from DP_IBKR__READONLY or False)
        """
        self.ib = IB()

        # Load configuration from environment variables with fallbacks
        self.host = host or os.environ.get('DP_BROKER__HOST', '127.0.0.1')
        self.port = int(port or os.environ.get('DP_BROKER__PORT', '7497'))
        self.clientId = int(clientId or os.environ.get('DP_IBKR__CLIENT_ID', '1'))
        self.timeout = int(timeout or os.environ.get('DP_IBKR__TIMEOUT', '30'))
        self.readonly = readonly or os.environ.get('DP_IBKR__READONLY', 'false').lower() in ('true', '1', 'yes')

        print(f"IBKR Handler initialized (host={self.host}, port={self.port}, clientId={self.clientId}, readonly={self.readonly})")

    def connect(self):
        """Establishes connection to TWS or IB Gateway."""
        if not self.ib.isConnected():
            try:
                self.ib.connect(self.host, self.port, self.clientId, timeout=self.timeout, readonly=self.readonly)
                status = "read-only" if self.readonly else "live"
                print(f"✅ Successfully connected to IBKR ({status} mode).")
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                raise
        else:
            print("Already connected.")

    def disconnect(self):
        """Disconnects from TWS or IB Gateway."""
        if self.ib.isConnected():
            self.ib.disconnect()
            print("Disconnected from IBKR.")

# דוגמת שימוש (שתוכל להריץ כדי לבדוק)
if __name__ == '__main__':
    handler = IBKRHandler()
    handler.connect()
    # כאן תוכל להוסיף קריאות לבדיקת חשבון, פוזיציות וכו'
    handler.disconnect()
