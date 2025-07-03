def convert_seconds(total_seconds):
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return hours, minutes, seconds


total = int(input("Enter time in seconds: "))
h, m, s = convert_seconds(total)
print(f"{total} seconds = {h} hours, {m} minutes, and {s} seconds")
