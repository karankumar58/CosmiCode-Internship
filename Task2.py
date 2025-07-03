def power(a, b):
    return a ** b

def modulo(a, b):
    return a % b

number1 = int(input("Enter number one: "))
number2 = int(input("Enter number two: "))

print(f"{number1} raised to the power {number2} is: {power(number1, number2)}")
print(f"Modulo of {number1} % {number2} is: {modulo(number1, number2)}")
