import requests
from fpdf import FPDF
from bs4 import BeautifulSoup
from datetime import datetime
import re
import os

COMPANIES_HOUSE_API_KEY = '635aca27-e670-4e63-a58f-5a4327649100'
BASE_CH_URL = 'https://api.company-information.service.gov.uk'

def sanitize_text(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

class CustomPDF(FPDF):
    def header(self):
        if os.path.exists("pali_background.png"):
            self.image("pali_background.png", x=0, y=0, w=210, h=297)
        self.set_y(10)

def get_company_number(name):
    url = f"{BASE_CH_URL}/search/companies"
    params = {"q": name}
    r = requests.get(url, params=params, auth=(COMPANIES_HOUSE_API_KEY, ''))
    items = r.json().get("items", [])
    if not items:
        return None
    return items[0]["company_number"], items[0]["title"]

def get_insolvency_info(company_number):
    url = f"{BASE_CH_URL}/company/{company_number}/insolvency"
    r = requests.get(url, auth=(COMPANIES_HOUSE_API_KEY, ''))
    return r.json() if r.status_code == 200 else {}

def get_filing_history(company_number):
    url = f"{BASE_CH_URL}/company/{company_number}/filing-history"
    r = requests.get(url, auth=(COMPANIES_HOUSE_API_KEY, ''), params={"items_per_page": 100})
    if r.status_code != 200:
        return []
    filings = r.json().get("items", [])
    keywords = [
        "winding up",
        "notice of intention to appoint administrator",
        "administration order",
        "appointment of administrator",
        "application for administration"
    ]
    return [f for f in filings if any(kw.lower() in f.get("description", "").lower() for kw in keywords)]

def search_london_gazette(company_name):
    query = company_name.replace(' ', '+')
    url = f"https://www.thegazette.co.uk/all-notices/notice?text={query}"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    notices = []
    for article in soup.select("article.notice")[:5]:
        title = article.find("h3").get_text(strip=True)
        date = article.find("time").get_text(strip=True)
        link = "https://www.thegazette.co.uk" + article.find("a")["href"]
        notices.append({"title": title, "date": date, "link": link})
    return notices

def format_insolvency_case_summary(case):
    summary = "\n**Insolvency Case**\n"
    for event in case.get('dates', []):
        event_type = event['type'].replace('-', ' ').capitalize()
        event_date = datetime.strptime(event['date'], "%Y-%m-%d").strftime("%d %B %Y")
        summary += f"{event_type}: {event_date}\n"
    return summary

def format_filing_summary(filings):
    summaries = []
    for f in filings:
        date = f.get('date', f.get('date_filed'))
        if date:
            try:
                formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d %B %Y")
            except:
                formatted_date = date
        else:
            formatted_date = "Unknown date"
        summaries.append(f"\n**Filing**\nDescription: {f['description']}\nDate: {formatted_date}")
    return summaries

def format_gazette_summary(gazette):
    summaries = []
    for notice in gazette:
        summaries.append(f"\n**Gazette Notice**\nTitle: {notice['title']}\nDate: {notice['date']}")
    return summaries

def generate_pdf_report(company_name, insolvency_info, filings, gazette, filename):
    pdf = CustomPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=8)

# Title Page
    pdf.add_page()
    pdf.set_y(60)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, sanitize_text("Report Produced By:"), ln=True)
    pdf.set_font("Arial", size=8)
    pdf.multi_cell(0, 5, sanitize_text("Pali Ltd\n2-4 Croxteth Avenue\nWallasey\nCH44 5UL"))
    pdf.ln(8)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, sanitize_text(f"Date of Report: {datetime.now().strftime('%d %B %Y')}"), ln=True)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, sanitize_text(f"Company against which enquiries are made: {company_name}"), ln=True)
    pdf.ln(12)

    def draw_status_box(label, has_entries, y):
        pdf.set_y(y)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(100, 10, sanitize_text(label), border=1)
        fill_color = (255, 255, 0) if has_entries else (144, 238, 144)
        pdf.set_fill_color(*fill_color)
        pdf.cell(20, 10, '', border=1, fill=True, ln=True)

    draw_status_box("Insolvency Cases Found", len(insolvency_info.get('cases', [])) > 0, pdf.get_y())
    draw_status_box("Relevant Filings Found", len(filings) > 0, pdf.get_y())
    draw_status_box("London Gazette Notices Found", len(gazette) > 0, pdf.get_y())

    # Explanation Page
    pdf.add_page()
    pdf.set_y(80)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, sanitize_text("Summary of Findings"), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=8)
    if insolvency_info.get("cases"):
        for case in insolvency_info.get("cases"):
            summary = format_insolvency_case_summary(case)
            for line in summary.strip().split('\n'):
                if line.startswith("**"):
                    pdf.set_font("Arial", 'B', 8)
                    pdf.cell(0, 10, sanitize_text(line.replace("**", "")), ln=True, align='C')
                    pdf.set_font("Arial", size=8)
                else:
                    pdf.cell(0, 10, sanitize_text(line), ln=True, align='C')
            pdf.ln(5)
    if filings:
        for entry in format_filing_summary(filings):
            for line in entry.split('\n'):
                if line.startswith("**"):
                    pdf.set_font("Arial", 'B', 8)
                    pdf.cell(0, 10, sanitize_text(line.replace("**", "")), ln=True, align='C')
                    pdf.set_font("Arial", size=8)
                else:
                    pdf.cell(0, 10, sanitize_text(line), ln=True, align='C')
            pdf.ln(5)
    if gazette:
        for entry in format_gazette_summary(gazette):
            for line in entry.split('\n'):
                if line.startswith("**"):
                    pdf.set_font("Arial", 'B', 8)
                    pdf.cell(0, 10, sanitize_text(line.replace("**", "")), ln=True, align='C')
                    pdf.set_font("Arial", size=8)
                else:
                    pdf.cell(0, 10, sanitize_text(line), ln=True, align='C')
            pdf.ln(5)
    if not insolvency_info.get("cases") and not filings and not gazette:
        pdf.cell(0, 10, sanitize_text("No records found."), ln=True, align='C')

    # Sources Page
    pdf.add_page()
    pdf.set_y(80)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, sanitize_text("Sources"), ln=True, align='C')
    pdf.ln(10)
    pdf.set_text_color(0, 0, 255)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(0, 8, sanitize_text("Companies House API"), ln=True, align='C', link="https://developer.company-information.service.gov.uk")
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, sanitize_text("The official UK government API for company financial and status data."), align='C')
    pdf.ln(5)
    pdf.set_text_color(0, 0, 255)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(0, 8, sanitize_text("The London Gazette"), ln=True, align='C', link="https://www.thegazette.co.uk")
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, sanitize_text("The UK’s official public record for legal, insolvency, and regulatory notices."), align='C')

    pdf.output(filename)

if __name__ == "__main__":
    input_name = input("Enter Company Name: ")
    result = get_company_number(input_name)
    if not result:
        print("Company not found.")
    else:
        number, official_name = result
        insolvency = get_insolvency_info(number)
        filings = get_filing_history(number)
        gazette = search_london_gazette(official_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^A-Za-z0-9]+', '_', official_name.strip())
        filename = f"{safe_name}_{timestamp}.pdf"
        generate_pdf_report(official_name, insolvency, filings, gazette, filename)
        print(f"Report generated: {filename}")
