alter table public.vacancies
  drop constraint if exists vacancies_canonical_title_check;

alter table public.vacancies
  add constraint vacancies_canonical_title_check
  check (
    canonical_title is null
    or canonical_title in (
      'Graphic Designer',
      'Brand Designer',
      'Visual Designer',
      'Communication Designer',
      'Digital Designer',
      'Marketing Designer',
      'Presentation Designer',
      'Editorial Designer',
      'Packaging Designer',
      'Information Designer',
      'Key Visual Designer',
      'Motion Designer',
      '3D Designer',
      'Web Designer',
      'UI Designer',
      'Illustrator',
      'Type Designer',
      'Art Director',
      'Creative Director',
      'Design Director',
      'Design Manager'
    )
  );

