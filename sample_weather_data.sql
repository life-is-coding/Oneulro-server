BEGIN;

INSERT INTO oneulro.app_user (
    social_provider,
    social_id,
    nickname
)
VALUES (
    'SAMPLE',
    'weather-sample-user',
    '날씨 테스트'
)
ON CONFLICT (social_provider, social_id)
DO UPDATE SET
    nickname = EXCLUDED.nickname,
    deleted_at = NULL,
    updated_at = now();

INSERT INTO oneulro.course (
    user_id,
    title,
    departure_station,
    start_date,
    end_date,
    total_days,
    visibility
)
SELECT
    u.user_id,
    '전국 주요역 날씨 샘플',
    '부산역',
    CURRENT_DATE,
    CURRENT_DATE + 4,
    5,
    'PRIVATE'
FROM oneulro.app_user u
WHERE u.social_provider = 'SAMPLE'
  AND u.social_id = 'weather-sample-user'
  AND NOT EXISTS (
      SELECT 1
      FROM oneulro.course c
      WHERE c.user_id = u.user_id
        AND c.title = '전국 주요역 날씨 샘플'
        AND c.deleted_at IS NULL
  );

INSERT INTO oneulro.course_stop (
    course_id,
    day_number,
    sequence,
    station_name,
    lat,
    lng
)
SELECT c.course_id, sample.day_number, 1, sample.station_name, sample.lat, sample.lng
FROM oneulro.course c
JOIN oneulro.app_user u ON u.user_id = c.user_id
CROSS JOIN (
    VALUES
        (1, '부산역',       35.1149550::numeric, 129.0415810::numeric),
        (2, '서울역',       37.5546780::numeric, 126.9706060::numeric),
        (3, '대전역',       36.3321790::numeric, 127.4348380::numeric),
        (4, '강릉역',       37.7640650::numeric, 128.8996290::numeric),
        (5, '여수엑스포역', 34.7527820::numeric, 127.7463060::numeric)
) AS sample(day_number, station_name, lat, lng)
WHERE u.social_provider = 'SAMPLE'
  AND u.social_id = 'weather-sample-user'
  AND c.title = '전국 주요역 날씨 샘플'
  AND c.deleted_at IS NULL
ON CONFLICT (course_id, day_number, sequence)
DO UPDATE SET
    station_name = EXCLUDED.station_name,
    lat = EXCLUDED.lat,
    lng = EXCLUDED.lng;

COMMIT;
