SELECT
    nconst,
    primary_name,
    birth_year,
    death_year,
    age_at_death,
    CASE
        WHEN birth_year IS NOT NULL THEN
            CASE
                WHEN birth_year >= 2010 THEN 'Gen Alpha'
                WHEN birth_year >= 1997 THEN 'Gen Z'
                WHEN birth_year >= 1981 THEN 'Millennial'
                WHEN birth_year >= 1965 THEN 'Gen X'
                WHEN birth_year >= 1946 THEN 'Boomer'
                ELSE 'Silent/Greatest'
            END
        ELSE NULL
    END AS generation,
    profession_list,
    known_for_titles
FROM {{ ref('int_person_details') }}
