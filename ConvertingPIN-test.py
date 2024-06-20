def convertToPinCode(inputString):
    # Dictionary to map written numbers to digits
    number_map = {
        "zero": "0", "one": "1", "two": "2", "three": "3",
        "four": "4", "five": "5", "six": "6", "seven": "7",
        "eight": "8", "nine": "9"
    }
    
    # Split the input string by spaces
    parts = inputString.split()
    
    # List to hold the PIN code digits
    pin_code = []
    
    # Iterate over each part
    for part in parts:
        # Remove any non-alphanumeric characters
        cleaned_part = ''.join(filter(str.isalnum, part))
        
        # Convert written numbers to digits if present in the map
        if cleaned_part in number_map:
            pin_code.append(number_map[cleaned_part])
        elif cleaned_part.isdigit():
            pin_code.append(cleaned_part)
    
    # Join the PIN code digits
    pin_code_str = ''.join(pin_code)
    
    # Check if the PIN code is exactly 4 digits
    if len(pin_code_str) == 4:
        print(pin_code_str)
        password = pin_code_str  # Set the password variable
        return True
    else:
        return False

# Example usage:
print(convertToPinCode("My PIN code is one 5 3 6"))  # Should return True
print(convertToPinCode("Enter the code: 7 two eight zero"))  # Should return True
print(convertToPinCode("Invalid code 12 34"))  # Should return False
