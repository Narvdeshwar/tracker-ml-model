import openpyxl

wb = openpyxl.load_workbook('Indian_IPO_ML_Research_Starter.xlsx')
for sheetname in ['IPO_Master', 'Listing_Outcomes', 'Source_Register', 'Data_Quality_Log']:
    ws = wb[sheetname]
    headers = [cell.value for cell in ws[1]]
    print(f"=== {sheetname} ({len(headers)} cols) ===")
    print(headers)
