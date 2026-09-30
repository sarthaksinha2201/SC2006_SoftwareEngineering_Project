# Which hospitals count for Healthcare

Decided 30 Sep 2026 (DECISIONS.md section 9). The Healthcare factor's "hospital" option measures straight-line distance to the nearest of the **9 public acute general hospitals**: Singapore General, Changi General, Tan Tock Seng, National University, Khoo Teck Puat, Ng Teng Fong General, Sengkang General, Woodlands and Alexandra.

## Why this definition

- **In an emergency you do not choose your hospital.** SCDF conveys emergency cases to public hospital emergency departments, so living beside a private hospital does not improve emergency access. That access is what this option measures.
- **Private hospitals do not have emergency departments.** By their own descriptions they run 24-hour urgent care centres or clinics, and MOH states that private hospitals "are not configured to provide the full range of emergency and trauma services".
- **Alexandra Hospital is included** although it has an urgent care centre rather than a full emergency department. It is a public general hospital, and the category only holds together if it includes all of them.
- Community, psychiatric and specialty hospitals and the prison medical facility are excluded. KK Women's and Children's has 24-hour emergency care for children and women only.
- Routine private care is covered by the GP clinics option.

The classification of all 31 MOH-licensed hospitals, with a source for every row, is in `data/reference/hospitals.csv`. The rule is `HOSPITAL_CATEGORIES` and `HOSPITAL_CARE_24H` in `gowhere/config.py`.

## The definition changes the answer: measured before choosing

Each alternative was built and compared with the adopted rule across all 32 in-scope areas:

| Alternative | Area medians changed | Areas changing rank | Largest rank shift | Largest score change | Biggest moves (adopted → alternative) |
|---|---|---|---|---|---|
| Emergency departments only (8, no Alexandra) | 3 | 10 | 7 | 2.26 | Queenstown 7→14 |
| Also private hospitals' 24-hour urgent care (17) | 13 | 30 | 23 | 7.42 | Marine Parade 31→8, Downtown Core 18→2, Tanglin 24→12, Rochor 8→1 |

Adding the private hospitals would move almost every area. They are all in the centre and east, so central areas would rise and heartland areas would fall. That size of change is why the definition had to be decided on purpose rather than left at a default.

The results show a note with the hospital option, so users who would use private care can see what the number covers.
