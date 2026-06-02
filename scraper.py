import requests
from bs4 import BeautifulSoup
import hashlib
import time

def scrape_indiabix_topic(url, max_questions=20):
    """
    Scrapes questions from an IndiaBix topic page.
    Each question dict contains:
      - id: unique hash (url + index)
      - question: question text
      - options: list of options text
      - answer: correct option letter (A, B, C, D, or E)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[-] Failed to fetch {url}. Status code: {response.status_code}")
            return []
    except Exception as e:
        print(f"[-] Error fetching {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # IndiaBix uses bix-div-container for questions in the new layout
    # and bix-tbl-container in the old layout
    containers = soup.find_all(class_='bix-div-container')
    if not containers:
        containers = soup.find_all(class_='bix-tbl-container')
        
    questions = []
    for idx, container in enumerate(containers):
        if len(questions) >= max_questions:
            break
            
        try:
            # 1. Parse question text
            qtxt_elem = container.find(class_='bix-td-qtxt')
            if not qtxt_elem:
                continue
            question_text = qtxt_elem.get_text(separator="\n", strip=True)
            
            # 2. Parse options dynamically (can be 4 or 5 options)
            options_table = container.find(class_='bix-tbl-options')
            if not options_table:
                options_table = container
                
            # In the new layout, the text is inside bix-td-option-val.
            # In the old layout, the text is inside bix-td-option.
            option_cells = options_table.find_all(class_='bix-td-option-val')
            if not option_cells:
                option_cells = options_table.find_all(class_='bix-td-option')
                
            if not option_cells:
                continue
                
            options = [cell.get_text(strip=True) for cell in option_cells]
            if len(options) < 2:
                continue # A question must have at least 2 options
                
            # 3. Parse correct answer (hidden input value, typically 'A', 'B', etc.)
            ans_input = container.find('input', class_='jq-hdnakq')
            correct_answer = ""
            if ans_input and ans_input.has_attr('value'):
                correct_answer = ans_input['value'].strip().upper()
                
            if not correct_answer:
                # Fallback to finding answers inside other hidden containers
                ans_div = container.find(class_='bix-div-answer')
                if ans_div:
                    ans_text = ans_div.get_text().strip().upper()
                    for char in ['A', 'B', 'C', 'D', 'E']:
                        if f"OPTION {char}" in ans_text or f"ANSWER: {char}" in ans_text:
                            correct_answer = char
                            break
            
            # If we still don't have a correct answer, skip this question
            if not correct_answer:
                continue
                
            # 4. Generate unique ID using MD5 hash of URL + index
            unique_str = f"{url}_{idx}_{question_text[:50]}"
            q_id = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
            
            questions.append({
                "id": q_id,
                "question": question_text,
                "options": options,
                "answer": correct_answer,
                "source_url": url
            })
            
        except Exception as ex:
            print(f"[-] Error parsing question container at index {idx}: {ex}")
            continue
            
    return questions

def run_test():
    """Test scraper on 3 different IndiaBix topic pages"""
    test_urls = [
        "https://www.indiabix.com/aptitude/problems-on-trains/",
        "https://www.indiabix.com/aptitude/height-and-distance/",
        "https://www.indiabix.com/aptitude/simple-interest/"
    ]
    
    print("[*] Starting Scraper Verification on 3 different topic pages...")
    for url in test_urls:
        print(f"\n[*] Scraping: {url}")
        questions = scrape_indiabix_topic(url, max_questions=3)
        print(f"[+] Scraped {len(questions)} questions.")
        for idx, q in enumerate(questions):
            print(f"  Q{idx+1} ID: {q['id']}")
            print(f"  Text: {q['question'][:120]}...")
            print(f"  Options ({len(q['options'])}): {q['options']}")
            print(f"  Correct Answer: {q['answer']}")
            print("-" * 40)
        time.sleep(1) # Polite scraping delay

if __name__ == "__main__":
    run_test()
