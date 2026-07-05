-- ============================================================
-- 내일로 앱 — 물리 데이터 모델 v2
-- PostgreSQL + PostGIS 기준
-- 전용 스키마: oneulro
-- 물리 FK 제약 없음
-- pgvector 미사용
-- ============================================================

CREATE SCHEMA IF NOT EXISTS oneulro;

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;

SET search_path TO oneulro, public;

-- ------------------------------------------------------------
-- updated_at 자동 갱신 함수
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION oneulro.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ------------------------------------------------------------
-- 1. USERS
-- ------------------------------------------------------------
CREATE TABLE oneulro.users (
    user_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kakao_id          VARCHAR(64)  NOT NULL,
    nickname          VARCHAR(50)  NOT NULL,
    profile_image_url VARCHAR(500),
    refresh_token     VARCHAR(512),
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at        TIMESTAMP,

    CONSTRAINT uq_user_kakao_id UNIQUE (kakao_id)
);

COMMENT ON TABLE oneulro.users IS '회원';


-- ------------------------------------------------------------
-- 2. SEARCH_PRESET
-- ------------------------------------------------------------
CREATE TABLE oneulro.search_preset (
    preset_id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id               BIGINT       NOT NULL,
    travel_days           SMALLINT,
    companion_type        VARCHAR(20),
    budget_range          VARCHAR(20),
    pet_allowed           BOOLEAN      NOT NULL DEFAULT FALSE,
    theme_tags            JSONB,
    natural_language_memo VARCHAR(500),
    updated_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_search_preset_user
ON oneulro.search_preset (user_id);

CREATE TRIGGER trg_search_preset_updated_at
BEFORE UPDATE ON oneulro.search_preset
FOR EACH ROW
EXECUTE FUNCTION oneulro.update_updated_at_column();

COMMENT ON TABLE oneulro.search_preset IS '코스 생성 입력 조건 프리셋';


-- ------------------------------------------------------------
-- 3. COURSE
-- ------------------------------------------------------------
CREATE TABLE oneulro.course (
    course_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           BIGINT       NOT NULL,
    preset_id         BIGINT,
    title             VARCHAR(100) NOT NULL,
    departure_station VARCHAR(50)  NOT NULL,
    total_days        SMALLINT     NOT NULL DEFAULT 1,
    status            VARCHAR(20)  NOT NULL DEFAULT 'DONE',
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_course_user
ON oneulro.course (user_id, created_at DESC);

CREATE INDEX idx_course_preset
ON oneulro.course (preset_id);

COMMENT ON TABLE oneulro.course IS '생성된 여행 코스';


-- ------------------------------------------------------------
-- 4. COURSE_STOP
-- ------------------------------------------------------------
CREATE TABLE oneulro.course_stop (
    stop_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id    BIGINT      NOT NULL,
    day_number   SMALLINT    NOT NULL DEFAULT 1,
    sequence     SMALLINT    NOT NULL,
    station_name VARCHAR(50) NOT NULL,
    train_type   VARCHAR(20),
    seat_class   VARCHAR(20),
    arrive_at    TIME,
    depart_at    TIME,
    stay_minutes INTEGER,

    CONSTRAINT uq_stop_order UNIQUE (course_id, day_number, sequence)
);

CREATE INDEX idx_course_stop_course
ON oneulro.course_stop (course_id);

COMMENT ON TABLE oneulro.course_stop IS '코스 경유 역 및 열차 정보';


-- ------------------------------------------------------------
-- 5. PLACE
-- PostGIS 적용: lat/lng 대신 location 사용
-- 좌표 입력 순서: longitude, latitude
-- ------------------------------------------------------------
CREATE TABLE oneulro.place (
    place_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stop_id         BIGINT       NOT NULL,
    tour_content_id VARCHAR(20),
    name            VARCHAR(100) NOT NULL,
    category        VARCHAR(50),
    address         VARCHAR(200),
    location        GEOGRAPHY(POINT, 4326),
    pet_allowed     BOOLEAN,
    walk_minutes    INTEGER,
    image_url       VARCHAR(500),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_place_stop
ON oneulro.place (stop_id);

CREATE INDEX idx_place_tour_content
ON oneulro.place (tour_content_id);

CREATE INDEX idx_place_location_gist
ON oneulro.place USING GIST (location);

COMMENT ON TABLE oneulro.place IS '코스 내 추천 장소 (TourAPI 캐시)';


-- ------------------------------------------------------------
-- 6. SAVED_COURSE
-- ------------------------------------------------------------
CREATE TABLE oneulro.saved_course (
    saved_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id   BIGINT    NOT NULL,
    course_id BIGINT    NOT NULL,
    saved_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_saved UNIQUE (user_id, course_id)
);

CREATE INDEX idx_saved_user
ON oneulro.saved_course (user_id, saved_at DESC);

CREATE INDEX idx_saved_course
ON oneulro.saved_course (course_id);

COMMENT ON TABLE oneulro.saved_course IS '회원이 저장한 코스';


-- ------------------------------------------------------------
-- 7. SHARE_LINK
-- ------------------------------------------------------------
CREATE TABLE oneulro.share_link (
    link_id    BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id  BIGINT      NOT NULL,
    token      VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP   NOT NULL,
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_share_token UNIQUE (token)
);

CREATE INDEX idx_share_course
ON oneulro.share_link (course_id);

CREATE INDEX idx_share_token_exp
ON oneulro.share_link (token, expires_at);

COMMENT ON TABLE oneulro.share_link IS '코스 공유 링크 토큰';
