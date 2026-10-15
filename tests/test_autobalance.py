from server import auto_balance, AutoBalanceInput

payload = AutoBalanceInput(
    calcium=100,
    magnesium=50,
    sodium=150,
    chloride=100,
    sulfate=100,
    bicarbonate=50,
    ph=7.5,
    temperature=25
)

result = auto_balance(payload)
print("Status:", result.status)
print("CBE%:", result.cbe_pct)
print("Injected Ion:", result.injected_ion)
print("Injected Amount:", result.injected_amount_mg_l)
print("Message:", result.message)
