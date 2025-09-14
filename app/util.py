import json

def readHeroNames(fileName: str) -> list[str]:
    try:
        with open(fileName, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: File '{fileName}' not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: File '{fileName}' is not valid JSON.")
        return []