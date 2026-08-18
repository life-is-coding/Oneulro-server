-- S-05 코스생성 결과 화면: 역 카드(이미지/혼잡도/혜택역) 지원
-- 역간 소요시간은 기존 course_stop.travel_minutes로 이미 커버됨.
--
-- 주의: 이 파일은 저장소에만 추가되며 자동으로 실행되지 않는다.
-- 실제 DB에는 검토 후 직접 적용할 것.

ALTER TABLE oneulro.course_stop
    ADD COLUMN image_url TEXT,
    ADD COLUMN congestion_score INTEGER,
    ADD COLUMN is_benefit_station BOOLEAN NOT NULL DEFAULT FALSE;
