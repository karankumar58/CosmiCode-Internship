import math


def area_trapezoid(base1, base2, height):
    return 0.5 * (base1 + base2) * height


def area_ellipse(a, b):
    return math.pi * a * b


print("Choose shape:\n1. Trapezoid\n2. Ellipse")
choice = input("Enter 1 or 2: ")

if choice == "1":
    base1 = float(input("Enter base1: "))
    base2 = float(input("Enter base2: "))
    height = float(input("Enter height: "))
    print(f"Area of trapezoid: {area_trapezoid(base1, base2, height):.2f}")
elif choice == "2":
    a = float(input("Enter semi-major axis (a): "))
    b = float(input("Enter semi-minor axis (b): "))
    print(f"Area of ellipse: {area_ellipse(a, b):.2f}")
else:
    print("Invalid choice.")
