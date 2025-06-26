from flask import Flask, render_template, request, redirect, url_for, session, send_file
from insolvency_report_tool import get_company_number, get_insolvency_info, get_filing_history, search_london_gazette, generate_pdf_report
from datetime import datetime
import re
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'
SHARED_PASSWORD = 'paliaccess'

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == SHARED_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Incorrect password')
    return render_template('login.html')

@app.route('/report', methods=['GET', 'POST'])
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))

    message = ''
    if request.method == 'POST':
        company_name = request.form.get('company')
        if not company_name:
            message = 'Please enter a company name.'
        else:
            result = get_company_number(company_name)
            if not result:
                message = 'Company not found. Please check the name and try again.'
            else:
                number, official_name = result
                insolvency = get_insolvency_info(number)
                filings = get_filing_history(number)
                gazette = search_london_gazette(official_name)

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_name = re.sub(r'[^A-Za-z0-9]+', '_', official_name.strip())
                filename = f"reports/{safe_name}_{timestamp}.pdf"

                os.makedirs("reports", exist_ok=True)
                generate_pdf_report(official_name, insolvency, filings, gazette, filename)
                return send_file(filename)

    return render_template('index.html', message=message)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
