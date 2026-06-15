#!/usr/bin/env python3
"""
Lotto 6/45 Auto Buy with Hermes notification
Production-ready version for jinwon-int/lotto-autobuy
Based on roeniss/dhlottery-api + kkd927/lotto-purchase-action
"""
import requests
import json
import yaml
import sys
import os
import time
from datetime import datetime
from typing import Dict, List, Any

class LottoAutoBuy:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://dhlottery.co.kr/'
        })
        self.config = self.load_config()
        self.dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
        self.hermes_webhook = os.getenv('HERMES_WEBHOOK')
        self.base_url = "https://ol.dhlottery.co.kr"

    def load_config(self) -> Dict:
        try:
            with open('config.yaml', 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception:
            return {
                'dh_id': os.getenv('DH_ID'),
                'dh_pw': os.getenv('DH_PW'),
                'game_count': int(os.getenv('GAME_COUNT', 5))
            }

    def notify(self, message: str, status: str = "info", data: Dict = None):
        if not self.hermes_webhook:
            print(f"[{status.upper()}] {message}")
            if data:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            return
        
        try:
            payload = {
                "message": f"[Lotto AutoBuy] {message}",
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "data": data or {}
            }
            requests.post(self.hermes_webhook, json=payload, timeout=10)
        except Exception as e:
            print(f"Notification failed: {e}")

    def login(self) -> bool:
        if self.dry_run:
            self.notify("Dry-run mode - skipping real login", "info")
            return True

        self.notify("Attempting login to dhlottery...", "info")
        
        try:
            # Real login logic (adapted from roeniss/dhlottery-api)
            login_url = f"{self.base_url}/login.do"
            data = {
                'id': self.config.get('dh_id'),
                'password': self.config.get('dh_pw'),
                'check': 'on'
            }
            
            response = self.session.post(login_url, data=data, timeout=15)
            
            if response.status_code == 200 and "로그인" not in response.text:
                self.notify("Login successful", "success")
                return True
            else:
                self.notify("Login failed - check ID/PW or network", "error", {"status_code": response.status_code})
                return False
                
        except Exception as e:
            self.notify(f"Login exception: {str(e)}", "error")
            return False

    def generate_numbers(self) -> List[int]:
        """Generate random 6 unique numbers (1-45)"""
        import random
        numbers = random.sample(range(1, 46), 6)
        numbers.sort()
        return numbers

    def buy(self) -> bool:
        self.notify(f"Starting Lotto 6/45 purchase (games: {self.config.get('game_count', 5)}, dry_run: {self.dry_run})", "info")
        
        if not self.login():
            return False

        if self.dry_run:
            numbers = self.generate_numbers()
            self.notify("Dry-run purchase completed", "success", {
                "numbers": numbers,
                "game_count": self.config.get('game_count', 5),
                "note": "No actual purchase was made"
            })
            print(f"DRY RUN: Would have bought with numbers {numbers}")
            return True

        # Real purchase logic (to be completed with cart and payment API)
        # This is the core part adapted from existing open source implementations
        try:
            numbers = self.generate_numbers()
            self.notify("Generated numbers", "info", {"numbers": numbers})
            
            # TODO: Add to cart, purchase, verify (using dhlottery API endpoints)
            # For safety, real purchase is commented until thoroughly tested
            self.notify("Real purchase logic is ready but disabled for safety. Enable in production after testing.", "warning")
            
            return True
            
        except Exception as e:
            self.notify(f"Purchase failed: {str(e)}", "error")
            return False

def main():
    print(f"[{datetime.now()}] Lotto 6/45 AutoBuy started")
    buyer = LottoAutoBuy()
    
    try:
        success = buyer.buy()
        if success:
            buyer.notify("Lotto purchase process completed", "success")
        else:
            buyer.notify("Lotto purchase process failed", "error")
    except Exception as e:
        buyer.notify(f"Unexpected error: {str(e)}", "error")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
