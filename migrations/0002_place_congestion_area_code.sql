-- 관광공사 "관광지 집중률(TatsCnctrRateService)" API 조회에 필요한 법정동 지역코드를
-- 장소 생성 시점에 함께 저장해둔다. (areaCd = 시/도, signguCd = 시/도+시군구 concat)
--
-- 주의: 이 파일은 저장소에만 추가되며 자동으로 실행되지 않는다.
-- 실제 DB에는 검토 후 직접 적용할 것.

ALTER TABLE oneulro.place
    ADD COLUMN area_cd VARCHAR(10),
    ADD COLUMN signgu_cd VARCHAR(10);
