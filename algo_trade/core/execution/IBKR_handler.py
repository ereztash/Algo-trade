from ib_insync import IB, util

class IBKRHandler:
    def __init__(self, host='127.0.0.1', port=7497, clientId=1):
        self.ib = IB()
        self.host = host
        self.port = port
        self.clientId = clientId
        print("IBKR Handler initialized.")

    def connect(self):
        """Establishes connection to TWS or IB Gateway."""
        if not self.ib.isConnected():
            try:
                self.ib.connect(self.host, self.port, self.clientId)
                print("✅ Successfully connected to IBKR.")
            except Exception as e:
                print(f"❌ Connection failed: {e}")
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
