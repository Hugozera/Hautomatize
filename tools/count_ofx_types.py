import os
from decimal import Decimal
p = r"c:\Hautomatize\media\conversor\originais\processing_test\STONE_AGOSTO_TODO.ofx"
if not os.path.exists(p):
    print('OFX not found:', p)
    raise SystemExit(1)

debit_count = 0
credit_count = 0
debit_sum = Decimal('0.00')
credit_sum = Decimal('0.00')

with open(p, 'r', encoding='utf-8', errors='replace') as f:
    inside = False
    trntype = None
    amount = None
    for line in f:
        line = line.strip()
        if line.upper() == '<STMTTRN>':
            inside = True
            trntype = None
            amount = None
            continue
        if line.upper() == '</STMTTRN>':
            if trntype and amount is not None:
                # normalize amount: replace comma with dot and remove thousand separators
                amt = amount.replace('.', '').replace(',', '.')
                try:
                    val = Decimal(amt)
                except Exception:
                    val = Decimal('0.00')
                if trntype.upper() == 'DEBIT':
                    debit_count += 1
                    debit_sum += val
                else:
                    credit_count += 1
                    credit_sum += val
            inside = False
            trntype = None
            amount = None
            continue
        if inside:
            if line.startswith('<TRNTYPE>'):
                trntype = line.replace('<TRNTYPE>', '').replace('</TRNTYPE>', '').strip()
            if line.startswith('<TRNAMT>'):
                amount = line.replace('<TRNAMT>', '').replace('</TRNAMT>', '').strip()

print('DEBIT count:', debit_count)
print('CREDIT count:', credit_count)
print('DEBIT sum:', f'{debit_sum:.2f}')
print('CREDIT sum:', f'{credit_sum:.2f}')
print('TOTAL transactions:', debit_count + credit_count)
