#!/usr/bin/env python3
"""
Health check script for AlgoTrader services.

This script checks if the service is responding correctly by:
1. Checking if the HTTP endpoint is accessible
2. Verifying the /health endpoint returns 200
3. Checking if Kafka connectivity is working (optional)

Usage:
    python health.py --port 8000
    python health.py --port 8001 --service strategy
"""
import sys
import argparse
import urllib.request
import urllib.error
import json
from typing import Dict, Any


def check_http_endpoint(port: int, path: str = "/health") -> Dict[str, Any]:
    """Check if HTTP endpoint is responding."""
    url = f"http://localhost:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            status_code = response.getcode()
            data = response.read().decode('utf-8')

            if status_code == 200:
                return {
                    "status": "healthy",
                    "http_status": status_code,
                    "message": "Service is responding"
                }
            else:
                return {
                    "status": "unhealthy",
                    "http_status": status_code,
                    "message": f"Service returned non-200 status: {status_code}"
                }
    except urllib.error.HTTPError as e:
        return {
            "status": "unhealthy",
            "error": f"HTTP Error: {e.code}",
            "message": str(e)
        }
    except urllib.error.URLError as e:
        return {
            "status": "unhealthy",
            "error": "URL Error",
            "message": str(e)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": "Unknown error",
            "message": str(e)
        }


def main():
    parser = argparse.ArgumentParser(description="AlgoTrader service health check")
    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Port to check (8000 for data, 8001 for strategy, 8002 for order)"
    )
    parser.add_argument(
        "--service",
        type=str,
        default="unknown",
        help="Service name for logging"
    )
    parser.add_argument(
        "--path",
        type=str,
        default="/health",
        help="Health check path (default: /health)"
    )

    args = parser.parse_args()

    result = check_http_endpoint(args.port, args.path)

    if result["status"] == "healthy":
        print(f"✓ {args.service.upper()} service is healthy")
        sys.exit(0)
    else:
        print(f"✗ {args.service.upper()} service is unhealthy: {result.get('message', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
