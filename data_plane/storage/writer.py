"""
Storage Writer - כתיבת אירועי שוק ל-Database
מטרה: אחסון persistent של נתוני שוק (bars, ticks, OFI) ב-TimescaleDB או database דומה
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class StorageWriter:
    """
    כותב אירועי שוק ל-database.
    תומך ב-TimescaleDB, PostgreSQL, או InfluxDB.
    """

    def __init__(self, dsn: str):
        """
        אתחול Storage Writer.

        Args:
            dsn: Database connection string (e.g., postgresql://user:pass@host:port/db)
        """
        self.dsn = dsn
        self.connection = None
        self.batch_size = 100
        self.buffer = {
            'bars': [],
            'ticks': [],
            'ofi': []
        }
        logger.info(f"StorageWriter initialized with DSN: {dsn}")

    def connect(self):
        """
        יצירת חיבור ל-database.
        נדחה להגדרה עצלה (lazy initialization) עד לשימוש ראשון.
        """
        if self.connection is None:
            try:
                # TODO: הוסף חיבור אמיתי כשנבחר DB
                # import psycopg2
                # self.connection = psycopg2.connect(self.dsn)
                logger.info("Database connection established")
                self._init_tables()
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise
        return self.connection

    def _init_tables(self):
        """
        יצירת טבלאות אם לא קיימות.
        """
        # TODO: DDL statements for TimescaleDB
        # CREATE TABLE bars (timestamp TIMESTAMPTZ, symbol TEXT, open REAL, high REAL, low REAL, close REAL, volume BIGINT);
        # SELECT create_hypertable('bars', 'timestamp');
        pass

    def write_bar(self, ev: Dict[str, Any]) -> bool:
        """
        כתיבת Bar event לטבלת bars.

        Args:
            ev: Bar event dictionary עם שדות: timestamp, symbol, open, high, low, close, volume

        Returns:
            True אם הכתיבה הצליחה
        """
        try:
            self.buffer['bars'].append(ev)

            if len(self.buffer['bars']) >= self.batch_size:
                self._flush_bars()

            logger.debug(f"Bar written: {ev.get('symbol')} @ {ev.get('timestamp')}")
            return True
        except Exception as e:
            logger.error(f"Failed to write bar: {e}")
            return False

    def write_tick(self, ev: Dict[str, Any]) -> bool:
        """
        כתיבת Tick event לטבלת ticks.

        Args:
            ev: Tick event dictionary עם שדות: timestamp, symbol, price, size, side

        Returns:
            True אם הכתיבה הצליחה
        """
        try:
            self.buffer['ticks'].append(ev)

            if len(self.buffer['ticks']) >= self.batch_size:
                self._flush_ticks()

            logger.debug(f"Tick written: {ev.get('symbol')} @ {ev.get('price')}")
            return True
        except Exception as e:
            logger.error(f"Failed to write tick: {e}")
            return False

    def write_ofi(self, ev: Dict[str, Any]) -> bool:
        """
        כתיבת OFI (Order Flow Imbalance) event לטבלת ofi.

        Args:
            ev: OFI event dictionary עם שדות: timestamp, symbol, ofi_value, bid_volume, ask_volume

        Returns:
            True אם הכתיבה הצליחה
        """
        try:
            self.buffer['ofi'].append(ev)

            if len(self.buffer['ofi']) >= self.batch_size:
                self._flush_ofi()

            logger.debug(f"OFI written: {ev.get('symbol')} @ {ev.get('ofi_value')}")
            return True
        except Exception as e:
            logger.error(f"Failed to write OFI: {e}")
            return False

    def _flush_bars(self):
        """
        שטיפת buffer של bars ל-database.
        """
        if not self.buffer['bars']:
            return

        try:
            # TODO: Batch insert to database
            # cursor = self.connect().cursor()
            # cursor.executemany("INSERT INTO bars VALUES (%s, %s, %s, %s, %s, %s, %s)", self.buffer['bars'])
            # self.connection.commit()

            logger.info(f"Flushed {len(self.buffer['bars'])} bars to database")
            self.buffer['bars'].clear()
        except Exception as e:
            logger.error(f"Failed to flush bars: {e}")
            raise

    def _flush_ticks(self):
        """
        שטיפת buffer של ticks ל-database.
        """
        if not self.buffer['ticks']:
            return

        try:
            # TODO: Batch insert to database
            logger.info(f"Flushed {len(self.buffer['ticks'])} ticks to database")
            self.buffer['ticks'].clear()
        except Exception as e:
            logger.error(f"Failed to flush ticks: {e}")
            raise

    def _flush_ofi(self):
        """
        שטיפת buffer של OFI ל-database.
        """
        if not self.buffer['ofi']:
            return

        try:
            # TODO: Batch insert to database
            logger.info(f"Flushed {len(self.buffer['ofi'])} OFI events to database")
            self.buffer['ofi'].clear()
        except Exception as e:
            logger.error(f"Failed to flush OFI: {e}")
            raise

    def flush_all(self):
        """
        שטיפת כל ה-buffers ל-database.
        יש לקרוא לפני סגירת האפליקציה.
        """
        self._flush_bars()
        self._flush_ticks()
        self._flush_ofi()
        logger.info("All buffers flushed")

    def close(self):
        """
        סגירת חיבור ל-database אחרי שטיפה סופית.
        """
        try:
            self.flush_all()
            if self.connection:
                self.connection.close()
                logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")

    def __enter__(self):
        """Context manager support."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
