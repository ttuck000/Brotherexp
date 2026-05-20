from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import login_required
import pyodbc
import pandas as pd
from io import BytesIO

acc = Blueprint('accounting', __name__)

# 회계 실적 관리
@acc.route('/')
@login_required
def account_actual_list():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Account_Actual")
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('accounting/list.html', items=items)

@acc.route('/account_actual/add', methods=['GET', 'POST'])
@login_required
def account_actual_add():
    if request.method == 'POST':
        id_val        = request.form['id']
        cost_center   = request.form['cost_center']
        actual_type   = request.form['actual_type']
        actual_code   = request.form['actual_code']
        billing_date  = request.form['billing_date']
        key_date      = request.form['key_date']
        vat_type      = request.form['vat_type']
        vat_rate      = request.form['vat_rate']
        wht_rate      = request.form['wht_rate']
        total_amount  = request.form['total_amount']
        vat           = request.form['vat']
        wht           = request.form['wht']
        before_vat_amt= request.form['before_vat_amt']
        payment       = request.form['payment']
        account       = request.form['account']
        remark        = request.form['remark']

        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Account_Actual (
                ID, COST_CENTER, Actual_TYPE, Actual_Code, BILLING_DATE, KEY_DATE,
                VAT_TYPE, VAT_RATE, WHT_RATE, TOTAL_AMOUNT, VAT, WHT,
                BEFORE_VAT_AMT, PAYMENT, Account, REMARK
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_val, cost_center, actual_type, actual_code, billing_date, key_date,
            vat_type, vat_rate, wht_rate, total_amount, vat, wht,
            before_vat_amt, payment, account, remark
        ))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Account Actual record added successfully')
        return redirect(url_for('accounting.account_actual_list'))

    return render_template('accounting/new.html')

@acc.route('/account_actual/edit/<id_val>', methods=['GET', 'POST'])
@login_required
def account_actual_edit(id_val):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    if request.method == 'POST':
        cost_center   = request.form['cost_center']
        actual_type   = request.form['actual_type']
        actual_code   = request.form['actual_code']
        billing_date  = request.form['billing_date']
        key_date      = request.form['key_date']
        vat_type      = request.form['vat_type']
        vat_rate      = request.form['vat_rate']
        wht_rate      = request.form['wht_rate']
        total_amount  = request.form['total_amount']
        vat           = request.form['vat']
        wht           = request.form['wht']
        before_vat_amt= request.form['before_vat_amt']
        payment       = request.form['payment']
        account       = request.form['account']
        remark        = request.form['remark']

        cursor.execute("""
            UPDATE Account_Actual
            SET COST_CENTER=?, Actual_TYPE=?, Actual_Code=?, BILLING_DATE=?, KEY_DATE=?,
                VAT_TYPE=?, VAT_RATE=?, WHT_RATE=?, TOTAL_AMOUNT=?, VAT=?, WHT=?,
                BEFORE_VAT_AMT=?, PAYMENT=?, Account=?, REMARK=?
            WHERE ID=?
        """, (
            cost_center, actual_type, actual_code, billing_date, key_date,
            vat_type, vat_rate, wht_rate, total_amount, vat, wht,
            before_vat_amt, payment, account, remark, id_val
        ))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Account Actual record updated successfully')
        return redirect(url_for('accounting.account_actual_list'))

    # GET 요청일 때 기존 데이터 불러오기
    cursor.execute("SELECT * FROM Account_Actual WHERE ID=?", (id_val,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return render_template('errors/404.html'), 404

    return render_template('accounting/edit.html', item=row)

