-- ============================================================
-- Playerbot 캐릭터 이름 및 "누구의 소환수" 주인 이름 한글 갱신
-- Target: AzerothCore Playerbots / MySQL 8.x
--
-- 중요:
--   1) worldserver.exe와 authserver.exe를 종료한 상태에서 실행하세요.
--   2) "누구의 소환수"에서 누구 부분은 character_pet에 별도로
--      저장되지 않고 characters.name을 사용하므로, 봇 이름을 바꾸면
--      소환수 아래의 주인 이름도 함께 바뀝니다.
--   3) 소환수 자체 이름(character_pet.name)은 변경하지 않습니다.
-- ============================================================

SET NAMES utf8mb4;
USE `acore_characters`;

-- 최초 변경 전 이름을 보존하는 영구 복구 테이블입니다.
CREATE TABLE IF NOT EXISTS `zz_playerbot_name_kr_backup` (
    `guid` INT UNSIGNED NOT NULL,
    `old_name` VARCHAR(12) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    `new_name` VARCHAR(12) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    `backup_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`guid`),
    KEY `idx_new_name` (`new_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

DROP PROCEDURE IF EXISTS `sp_update_rndbot_owner_names_kr`;

DELIMITER $$

CREATE PROCEDURE `sp_update_rndbot_owner_names_kr`()
update_block: BEGIN
    DECLARE v_target_count INT DEFAULT 0;
    DECLARE v_mapped_count INT DEFAULT 0;
    DECLARE v_updated_count INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        DROP TEMPORARY TABLE IF EXISTS `tmp_playerbot_name_kr_map`;
        RESIGNAL;
    END;

    DROP TEMPORARY TABLE IF EXISTS `tmp_playerbot_name_kr_map`;

    CREATE TEMPORARY TABLE `tmp_playerbot_name_kr_map` (
        `guid` INT UNSIGNED NOT NULL,
        `old_name` VARCHAR(12) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
        `new_name` VARCHAR(12) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
        PRIMARY KEY (`guid`),
        UNIQUE KEY `uq_new_name` (`new_name`)
    ) ENGINE=InnoDB;

    -- 아직 한글 이름이 아닌 RNDBOT 캐릭터만 대상으로 지정합니다.
    SELECT COUNT(*)
      INTO v_target_count
      FROM `acore_characters`.`characters` c
      JOIN `acore_auth`.`account` a ON a.`id` = c.`account`
     WHERE a.`username` LIKE 'RNDBOT%'
       AND NOT (c.`name` REGEXP '[가-힣]');

    IF v_target_count = 0 THEN
        DROP TEMPORARY TABLE IF EXISTS `tmp_playerbot_name_kr_map`;
        LEAVE update_block;
    END IF;

    -- 봇 GUID와 사용 가능한 한글 이름에 각각 순번을 부여해 1:1 매칭합니다.
    -- 현재 어떤 캐릭터가 이미 사용 중인 이름은 후보에서 제외합니다.
    INSERT INTO `tmp_playerbot_name_kr_map` (`guid`, `old_name`, `new_name`)
    SELECT bots.`guid`, bots.`old_name`, names_kr.`new_name`
      FROM
      (
          SELECT c.`guid`, c.`name` AS `old_name`,
                 ROW_NUMBER() OVER (ORDER BY c.`guid`) AS `rn`
            FROM `acore_characters`.`characters` c
            JOIN `acore_auth`.`account` a ON a.`id` = c.`account`
           WHERE a.`username` LIKE 'RNDBOT%'
             AND NOT (c.`name` REGEXP '[가-힣]')
      ) bots
      JOIN
      (
          SELECT pn.`name` AS `new_name`,
                 ROW_NUMBER() OVER (ORDER BY pn.`name_id`) AS `rn`
            FROM `acore_characters`.`playerbots_names` pn
           WHERE pn.`name` REGEXP '^[가-힣]{2,12}$'
             AND NOT EXISTS
                 (
                     SELECT 1
                       FROM `acore_characters`.`characters` used_name
                      WHERE used_name.`name` = pn.`name`
                 )
      ) names_kr ON names_kr.`rn` = bots.`rn`;

    SELECT COUNT(*) INTO v_mapped_count
      FROM `tmp_playerbot_name_kr_map`;

    IF v_mapped_count <> v_target_count THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Playerbot 한글 이름 후보가 부족하여 변경을 중단했습니다.';
    END IF;

    START TRANSACTION;

    -- 동일 GUID가 이미 백업되어 있으면 최초 원본을 보존합니다.
    INSERT IGNORE INTO `zz_playerbot_name_kr_backup`
        (`guid`, `old_name`, `new_name`)
    SELECT `guid`, `old_name`, `new_name`
      FROM `tmp_playerbot_name_kr_map`;

    UPDATE `acore_characters`.`characters` c
    JOIN `tmp_playerbot_name_kr_map` m ON m.`guid` = c.`guid`
       SET c.`name` = m.`new_name`;

    SET v_updated_count = ROW_COUNT();

    IF v_updated_count <> v_target_count THEN
        ROLLBACK;
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = '예상 변경 수와 실제 변경 수가 달라 전체 변경을 취소했습니다.';
    END IF;

    COMMIT;

    DROP TEMPORARY TABLE IF EXISTS `tmp_playerbot_name_kr_map`;
END$$

DELIMITER ;

CALL `sp_update_rndbot_owner_names_kr`();
DROP PROCEDURE IF EXISTS `sp_update_rndbot_owner_names_kr`;

-- 수동 복구가 필요할 때 사용할 명령(자동 실행되지 않음):
-- UPDATE `acore_characters`.`characters` c
-- JOIN `acore_characters`.`zz_playerbot_name_kr_backup` b ON b.`guid` = c.`guid`
-- SET c.`name` = b.`old_name`;
