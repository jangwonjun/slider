synonym_groups = [
    ["주민등록증", "민증", "등록증"],
    ["롯데카드", "롯데"],
    ["삼성카드", "삼성"],
]

def find_canonical_name(name):
    name = name.strip()
    for group in synonym_groups:
        if name in group:
            return group[0]
    return name
