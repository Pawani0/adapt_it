import time
import uuid
import requests
import scraper
import tracker
import emailer
import config

def wait_for_server_awake(url, retries=5, delay=15):
    """Pings the quiz base URL to wake it up in case it is sleeping (e.g. Render free tier)."""
    print(f"[*] Checking if quiz server is awake: {url}...")
    for i in range(retries):
        try:
            # Send a simple GET to the home page or a dummy page
            response = requests.get(url, timeout=10)
            print(f"[+] Server is awake! (Status: {response.status_code})")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[-] Attempt {i+1}/{retries} failed to reach server. Retrying in {delay}s...")
            time.sleep(delay)
    return False

def orchestrate():
    """Main orchestrator routine run daily by GitHub Actions."""
    print("==================================================")
    print("      DAILY APTITUDE QUIZ AGENT - ORCHESTRATOR    ")
    print("==================================================")
    
    # Delegate to the new AI Orchestrator Agent
    from agent.orchestrator_agent import main as agent_main
    agent_main()

if __name__ == "__main__":
    orchestrate()

