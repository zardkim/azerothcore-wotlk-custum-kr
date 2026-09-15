SET NAMES utf8mb4;
SET @GH_OLD_SQL_MODE := @@SESSION.SQL_MODE;
SET @GH_OLD_FOREIGN_KEY_CHECKS := @@SESSION.FOREIGN_KEY_CHECKS;
SET SESSION FOREIGN_KEY_CHECKS = 0;


-- ============================================================================
-- 1. CHARACTERS DB: 길드하우스 소유 정보 테이블
-- ============================================================================
USE `acore_characters`;

CREATE TABLE IF NOT EXISTS `guild_house` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `guild` int(11) NOT NULL DEFAULT '0',
  `phase` int(11) NOT NULL,
  `map` int(11) NOT NULL DEFAULT '0',
  `positionX` float NOT NULL DEFAULT '0',
  `positionY` float NOT NULL DEFAULT '0',
  `positionZ` float NOT NULL DEFAULT '0',
  `orientation` float NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `guild` (`guild`)
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8;


-- ============================================================================
-- 2. WORLD DB: 충돌 데이터 즉시 삭제
-- ============================================================================
USE `acore_world`;

SET @C_TEMPLATE := 500030;
SET @GO_TEMPLATE := 500000;

-- 테이블 또는 컬럼이 존재하는 경우에만 대상 범위를 삭제합니다.
DROP PROCEDURE IF EXISTS `zz_gh_delete_range`;
DELIMITER $$
CREATE PROCEDURE `zz_gh_delete_range`(
    IN p_table  VARCHAR(64),
    IN p_column VARCHAR(64),
    IN p_min    BIGINT,
    IN p_max    BIGINT,
    IN p_extra  TEXT
)
proc: BEGIN
    DECLARE v_table_exists INT DEFAULT 0;
    DECLARE v_column_exists INT DEFAULT 0;

    IF p_table IS NULL OR p_column IS NULL THEN
        LEAVE proc;
    END IF;

    SELECT COUNT(*)
      INTO v_table_exists
      FROM information_schema.TABLES
     WHERE TABLE_SCHEMA = DATABASE()
       AND TABLE_NAME = p_table;

    IF v_table_exists = 0 THEN
        LEAVE proc;
    END IF;

    SELECT COUNT(*)
      INTO v_column_exists
      FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE()
       AND TABLE_NAME = p_table
       AND COLUMN_NAME = p_column;

    IF v_column_exists = 0 THEN
        LEAVE proc;
    END IF;

    SET @GH_WHERE = CONCAT(
        '`', p_column, '` BETWEEN ', p_min, ' AND ', p_max,
        IF(p_extra IS NULL OR p_extra = '', '', p_extra)
    );

    SET @GH_SQL = CONCAT(
        'DELETE FROM `', p_table, '` WHERE ', @GH_WHERE
    );
    PREPARE GH_STMT FROM @GH_SQL;
    EXECUTE GH_STMT;
    DEALLOCATE PREPARE GH_STMT;
END$$
DELIMITER ;

-- creature 스폰 테이블은 AzerothCore 버전에 따라 entry 컬럼이 id1/id/entry 중 하나입니다.
SET @GH_CREATURE_ENTRY_COL := NULL;
SELECT COLUMN_NAME
  INTO @GH_CREATURE_ENTRY_COL
  FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE()
   AND TABLE_NAME = 'creature'
   AND COLUMN_NAME IN ('id1', 'id', 'entry')
 ORDER BY FIELD(COLUMN_NAME, 'id1', 'id', 'entry')
 LIMIT 1;

CALL `zz_gh_delete_range`('creature', @GH_CREATURE_ENTRY_COL, 500030, 500032, '');

-- 기존 Creature 500030~500032와 관련 데이터를 즉시 제거합니다.
CALL `zz_gh_delete_range`('creature_template_locale',     'entry',       500030, 500032, '');
CALL `zz_gh_delete_range`('creature_template_addon',      'entry',       500030, 500032, '');
CALL `zz_gh_delete_range`('creature_template_model',      'CreatureID',  500030, 500032, '');
CALL `zz_gh_delete_range`('creature_template_movement',   'CreatureId',  500030, 500032, '');
CALL `zz_gh_delete_range`('creature_template_resistance', 'CreatureID',  500030, 500032, '');
CALL `zz_gh_delete_range`('creature_template_spell',      'CreatureID',  500030, 500032, '');
CALL `zz_gh_delete_range`('creature_equip_template',      'CreatureID',  500030, 500032, '');
CALL `zz_gh_delete_range`('npc_vendor',                   'entry',       500030, 500032, '');
CALL `zz_gh_delete_range`('creature_queststarter',        'id',          500030, 500032, '');
CALL `zz_gh_delete_range`('creature_questender',          'id',          500030, 500032, '');
CALL `zz_gh_delete_range`('creature_text',                'CreatureID',  500030, 500032, '');
CALL `zz_gh_delete_range`('creature_onkill_reputation',   'creature_id', 500030, 500032, '');
CALL `zz_gh_delete_range`('npc_spellclick_spells',        'npc_entry',   500030, 500032, '');
CALL `zz_gh_delete_range`('smart_scripts',                'entryorguid', 500030, 500032, ' AND `source_type` = 0');
CALL `zz_gh_delete_range`('creature_template',            'entry',       500030, 500032, '');

-- gameobject 스폰 테이블의 템플릿 컬럼도 버전에 따라 다를 수 있습니다.
SET @GH_GAMEOBJECT_ENTRY_COL := NULL;
SELECT COLUMN_NAME
  INTO @GH_GAMEOBJECT_ENTRY_COL
  FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE()
   AND TABLE_NAME = 'gameobject'
   AND COLUMN_NAME IN ('id', 'id1', 'entry')
 ORDER BY FIELD(COLUMN_NAME, 'id', 'id1', 'entry')
 LIMIT 1;

CALL `zz_gh_delete_range`('gameobject', @GH_GAMEOBJECT_ENTRY_COL, 500000, 500009, '');

-- 기존 GameObject 500000~500009와 관련 데이터를 즉시 제거합니다.
CALL `zz_gh_delete_range`('gameobject_template_locale', 'entry',       500000, 500009, '');
CALL `zz_gh_delete_range`('gameobject_template_addon',  'entry',       500000, 500009, '');
CALL `zz_gh_delete_range`('gameobject_queststarter',    'id',          500000, 500009, '');
CALL `zz_gh_delete_range`('gameobject_questender',      'id',          500000, 500009, '');
CALL `zz_gh_delete_range`('gameobject_loot_template',   'Entry',       500000, 500009, '');
CALL `zz_gh_delete_range`('smart_scripts',              'entryorguid', 500000, 500009, ' AND `source_type` = 1');
CALL `zz_gh_delete_range`('gameobject_template',        'entry',       500000, 500009, '');

-- 기존 구매/소환 목록을 모두 삭제한 뒤 공식 55개 항목으로 재구성합니다.
CALL `zz_gh_delete_range`('guild_house_spawns', 'id', 0, 4294967295, '');

DROP PROCEDURE IF EXISTS `zz_gh_delete_range`;


-- ============================================================================
-- 3. WORLD DB: 공식 길드하우스 Creature / GameObject 템플릿
-- ============================================================================
USE `acore_world`;

-- !!! NOTE: set these before running the queries in order to avoid conflicts !!!
SET @C_TEMPLATE = 500030;

DELETE FROM `creature_template` WHERE `entry` IN (
	@C_TEMPLATE + 0,
	@C_TEMPLATE + 1,
	@C_TEMPLATE + 2
);

INSERT INTO `creature_template` (`entry`, `difficulty_entry_1`, `difficulty_entry_2`, `difficulty_entry_3`, `KillCredit1`, `KillCredit2`, `name`, `subname`, `IconName`, `gossip_menu_id`, `minlevel`, `maxlevel`, `exp`, `faction`, `npcflag`, `speed_walk`, `speed_run`, `speed_swim`, `speed_flight`, `detection_range`, `rank`, `dmgschool`, `DamageModifier`, `BaseAttackTime`, `RangeAttackTime`, `BaseVariance`, `RangeVariance`, `unit_class`, `unit_flags`, `unit_flags2`, `dynamicflags`, `family`, `type`, `type_flags`, `lootid`, `pickpocketloot`, `skinloot`, `PetSpellDataId`, `VehicleId`, `mingold`, `maxgold`, `AIName`, `MovementType`, `HoverHeight`, `HealthModifier`, `ManaModifier`, `ArmorModifier`, `ExperienceModifier`, `RacialLeader`, `movementId`, `RegenHealth`, `flags_extra`, `ScriptName`, `VerifiedBuild`) VALUES
	(@C_TEMPLATE + 0, 0, 0, 0, 0, 0, 'Talamortis', 'Guild House Seller', '', 0, 35, 35, 0, 35, 0, 1, 1.14286, 1, 1, 20, 0, 0, 1, 2000, 2000, 1, 1, 1, 33536, 2048, 0, 0, 7, 4096, 0, 0, 0, 0, 0, 0, 0, '', 0, 1, 1, 1, 1, 1, 0, 0, 1, 0, 'GuildHouseSeller', 12340),
	(@C_TEMPLATE + 1, 0, 0, 0, 0, 0, 'Xrispins', 'Guild House Butler', '', 0, 35, 35, 0, 35, 0, 1, 1.14286, 1, 1, 20, 0, 0, 1, 2000, 2000, 1, 1, 1, 33536, 2048, 0, 0, 7, 4096, 0, 0, 0, 0, 0, 0, 0, '', 0, 1, 1, 1, 1, 1, 0, 0, 1, 0, 'GuildHouseSpawner', 12340),
	(@C_TEMPLATE + 2, 0, 0, 0, 0, 0, 'Innkeeper Monica', NULL, NULL, 0, 1, 2, 0, 35, 65536, 0.8, 0.28571, 1, 1, 20, 0, 0, 4.6, 2000, 1900, 1, 1, 1, 0, 2048, 0, 0, 7, 0, 0, 0, 0, 0, 0, 0, 0, '', 1, 1, 1, 1, 1, 1, 0, 70, 1, 2, 'npc_innkeeper', 12340);

DELETE FROM `creature_template_model` WHERE `CreatureID` IN (
	@C_TEMPLATE + 0,
	@C_TEMPLATE + 1,
	@C_TEMPLATE + 2
);

INSERT INTO `creature_template_model` (`CreatureID`, `Idx`, `CreatureDisplayID`, `DisplayScale`, `Probability`, `VerifiedBuild`) VALUES
    (@C_TEMPLATE + 0, 0, 25901, 1, 1, 0),
    (@C_TEMPLATE + 1, 0, 25901, 1, 1, 0),
    (@C_TEMPLATE + 2, 0, 18234, 1, 1, 0);

-- !!! NOTE: set these before running the queries in order to avoid conflicts !!!
SET @GO_TEMPLATE = 500000;

DELETE FROM `gameobject_template` WHERE `entry` IN (
    @GO_TEMPLATE + 0,
    @GO_TEMPLATE + 1,
    @GO_TEMPLATE + 2,
    @GO_TEMPLATE + 3,
    @GO_TEMPLATE + 4,
    @GO_TEMPLATE + 5,
    @GO_TEMPLATE + 6,
    @GO_TEMPLATE + 7,
    @GO_TEMPLATE + 8,
    @GO_TEMPLATE + 9
);

INSERT INTO `gameobject_template` (`entry`, `type`, `displayId`, `name`, `IconName`, `castBarCaption`, `unk1`, `size`, `Data0`, `Data1`, `Data2`, `Data3`, `Data4`, `Data5`, `Data6`, `Data7`, `Data8`, `Data9`, `Data10`, `Data11`, `Data12`, `Data13`, `Data14`, `Data15`, `Data16`, `Data17`, `Data18`, `Data19`, `Data20`, `Data21`, `Data22`, `Data23`, `AIName`, `ScriptName`, `VerifiedBuild`) VALUES
	(@GO_TEMPLATE + 0, 22, 4396, 'Portal to Stormwind', '', '', '', 1, 17334, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0),
	(@GO_TEMPLATE + 1, 22, 4393, 'Portal to Darnassus', '', '', '', 1, 17608, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0),
	(@GO_TEMPLATE + 2, 22, 6955, 'Portal to Exodar', '', '', '', 1, 32268, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0),
	(@GO_TEMPLATE + 3, 22, 4394, 'Portal to Ironforge', '', '', '', 1, 17607, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0),
	(@GO_TEMPLATE + 4, 22, 4395, 'Portal to Orgrimmar', '', '', '', 1, 17609, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0),
	(@GO_TEMPLATE + 5, 22, 6956, 'Portal to Silvermoon', '', '', '', 1, 32270, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0),
	(@GO_TEMPLATE + 6, 22, 4397, 'Portal to Thunder Bluff', '', '', '', 1, 17610, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0),
	(@GO_TEMPLATE + 7, 22, 4398, 'Portal to Undercity', '', '', '', 1, 17611, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0),
	(@GO_TEMPLATE + 8, 22, 7146, 'Portal to Shattrath', '', '', '', 1, 35718, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0),
	(@GO_TEMPLATE + 9, 22, 8111, 'Portal to Dalaran', '', '', '', 1, 53141, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0);


-- ============================================================================
-- 4. WORLD DB: 공식 길드하우스 구매/소환 목록 55개
-- ============================================================================
CREATE TABLE IF NOT EXISTS `guild_house_spawns` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `entry` int(11) NOT NULL DEFAULT '0',
  `posX` float NOT NULL DEFAULT '0',
  `posY` float NOT NULL DEFAULT '0',
  `posZ` float NOT NULL DEFAULT '0',
  `orientation` float NOT NULL DEFAULT '0',
  `comment` varchar(500) DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `entry` (`entry`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- !!! NOTE: set these before running the queries in order to avoid conflicts !!!
SET @C_TEMPLATE = 500030;
SET @GO_TEMPLATE = 500000;

REPLACE INTO `guild_house_spawns` (`id`, `entry`, `posX`, `posY`, `posZ`, `orientation`, `comment`) VALUES
  (1, 26327, 16216.5, 16279.4, 20.9306, 0.552869, 'Paladin Trainer'),
  (2, 26324, 16221.3, 16275.7, 20.9285, 1.37363, 'Druid Trainer'),
  (3, 26325, 16218.6, 16277, 20.9872, 0.967188, 'Hunter Trainer'),
  (4, 26326, 16224.9, 16274.9, 20.9319, 1.58765, 'Mage Trainer'),
  (5, 26328, 16227.9, 16275.9, 20.9254, 1.9941, 'Priest Trainer'),
  (6, 26329, 16231.4, 16278.1, 20.9222, 2.20026, 'Rogue Trainer'),
  (7, 26330, 16235.5, 16280.8, 20.9257, 2.18652, 'Shaman Trainer'),
  (8, 26331, 16240.8, 16283.3, 20.9299, 1.86843, 'Warlock Trainer'),
  (9, 26332, 16246.6, 16284.5, 20.9301, 1.68975, 'Warrior Trainer'),
  (10, @C_TEMPLATE + 2, 16218.9, 16284.5, 13.1761, 6.18533, 'Innkeeper'),
  (11, 30605, 16228.0, 16280.5, 13.1761, 2.98877, 'Banker'),
  (12, 29195, 16252.3, 16284.9, 20.9324, 1.79537, 'Death Knight Trainer'),
  (13, 2836, 16220.5, 16302.3, 13.176, 6.14647, 'Blacksmithing Trainer'),
  (14, 8128, 16220.2, 16299.6, 13.178, 6.22894, 'Mining Trainer'),
  (15, 8736, 16219.8, 16296.9, 13.1746, 6.24465, 'Engineering Trainer'),
  (16, 18774, 16222.4, 16293, 13.1813, 1.51263, 'Jewelcrafting Trainer (Alliance)'),
  (17, 18751, 16222.4, 16293, 13.1813, 1.51263, 'Jewelcrafting Trainer (Horde)'),
  (18, 18773, 16227.5, 16292.3, 13.1839, 1.49691, 'Enchanting Trainer (Alliance)'),
  (19, 18753, 16227.5, 16292.3, 13.1839, 1.49691, 'Enchanting Trainer (Horde)'),
  (20, 30721, 16231.6, 16301, 13.1757, 3.07372, 'Inscription Trainer (Alliance)'),
  (21, 30722, 16231.6, 16301, 13.1757, 3.07372, 'Inscription Trainer (Horde)'),
  (22, 19187, 16231.2, 16295, 13.1761, 3.06574, 'Leatherworking Trainer'),
  (23, 19180, 16228.9, 16304.7, 13.1819, 4.64831, 'Skinning Trainer'),
  (24, 19052, 16218.1, 16281.8, 13.1756, 6.1975, 'Alchemy Trainer'),
  (25, 908, 16218.3, 16284.3, 13.1756, 6.1975, 'Herbalism Trainer'),
  (26, 2627, 16220.4, 16278.7, 13.1756, 1.46157, 'Tailoring Trainer'),
  (27, 19184, 16225, 16310.9, 29.262, 6.22119, 'First Aid Trainer'),
  (28, 2834, 16225.3, 16313.9, 29.262, 6.28231, 'Fishing Trainer'),
  (29, 19185, 16227, 16278, 13.1762, 1.4872, 'Cooking Trainer'),
  (30, 8719, 16242, 16291.6, 22.9311, 1.52061, 'Alliance Auctioneer'),
  (31, 9856, 16242, 16291.6, 22.9311, 1.52061, 'Horde Auctioneer'),
  (32, 184137, 16220.3, 16272, 12.9736, 4.45592, 'Mailbox (Object)'),
  (33, 1685, 16253.8, 16294.3, 13.1758, 6.11938, 'Forge (Object)'),
  (34, 4087, 16254.4, 16298.7, 13.1758, 3.36027, 'Anvil (Object)'),
  (35, @GO_TEMPLATE + 0, 16232.9, 16264.1, 13.55570, 3.028813, 'Portal: Stormwind (Object)'),
  (36, @GO_TEMPLATE + 1, 16232.8, 16257.1, 13.93456, 3.028813, 'Portal: Darnassus (Object)'),
  (37, @GO_TEMPLATE + 2, 16231.3, 16254.2, 13.65647, 3.028813, 'Portal: Exodar (Object)'),
  (38, @GO_TEMPLATE + 3, 16233.4, 16260.6, 13.84770, 3.028813, 'Portal: Ironforge (Object)'),
  (39, @GO_TEMPLATE + 4, 16232.9, 16264.1, 13.55570, 3.028813, 'Portal: Orgrimmar (Object)'),
  (40, @GO_TEMPLATE + 5, 16231.3, 16254.2, 13.65647, 3.028813, 'Portal: Silvermoon (Object)'),
  (41, @GO_TEMPLATE + 6, 16233.4, 16260.6, 13.84770, 3.028813, 'Portal: Thunder Bluff (Object)'),
  (42, @GO_TEMPLATE + 7, 16232.8, 16257.1, 13.93456, 3.028813, 'Portal: Undercity (Object)'),
  (43, @GO_TEMPLATE + 8, 16211.1, 16266.9, 13.7458, 5.6724, 'Portal: Shattrath (Object)'),
  (44, @GO_TEMPLATE + 9, 16213.9, 16270.5, 13.1378, 5.4996, 'Portal: Dalaran (Object)'),
  (45, 187293, 16230.5, 16283.5, 13.9061, 3, 'Guild Vault (Object)'),
  (46, 28692, 16236.2, 16315.7, 20.8454, 4.64365, 'Trade Supplies'),
  (47, 28776, 16223.7, 16297.9, 20.8454, 6.17044, 'Tabard Vendor'),
  (48, 19572, 16230.2, 16316.1, 20.8455, 4.64365, 'Food & Drink Vendor'),
  (49, 6491, 16319.937, 16242.404, 24.4747, 2.206830, 'Spirit Healer'),
  (50, 191028, 16255.5, 16304.9, 20.9785, 2.97516, 'Barber Chair (Object)'),
  (51, 29636, 16233.2, 16315.9, 20.8454, 4.64365, 'Reagent Vendor'),
  (52, 29493, 16229.1, 16286.4, 13.176, 3.03831, 'Ammo & Repair Vendor'),
  (53, 28690, 16226.97, 16267.9, 13.15, 4.6533, 'Stable Master'),
  (54, 9858, 16238.2, 16291.8, 22.9306, 1.55386, 'Neutral Auctioneer'),
  (55, 2622, 16242.8, 16302.1, 13.176, 4.55570, 'Poisons Vendor');


-- 공식 innkeeper 보정 중 guild_house_spawns 좌표만 적용합니다.
-- 원본의 `UPDATE creature ... WHERE id=500032`는 최신/구형 스키마에서
-- 500032를 스폰 GUID로 잘못 해석할 수 있으므로 통합본에서는 제외했습니다.
UPDATE `guild_house_spawns`
   SET `posX` = 16221.91,
       `posY` = 16288.54,
       `posZ` = 13.17,
       `orientation` = 4.65
 WHERE `id` = 10;


-- ============================================================================
-- 5. WORLD DB: 기본 다국어/한국어 문자열 (재실행 가능)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `mod_guildhouse_locale` (
  `Id` INT UNSIGNED NOT NULL,
  `Locale` VARCHAR(4) NOT NULL,
  `Text` TEXT NOT NULL,
  PRIMARY KEY (`Id`, `Locale`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

REPLACE INTO `mod_guildhouse_locale` (`Id`, `Locale`, `Text`) VALUES
-- 1: Guild creation
(1, 'enUS', 'You now own a guild. You can purchase a Guild House!'),
(1, 'frFR', 'Vous possédez désormais une guilde. Vous pouvez acheter une maison de guilde !'),
(1, 'koKR', '이제 길드를 소유했습니다. 길드 하우스를 구매할 수 있습니다!'),
(1, 'deDE', 'Du besitzt nun eine Gilde. Du kannst ein Gildenhaus kaufen!'),
(1, 'zhCN', '你现在拥有一个公会。你可以购买公会大厅！'),
(1, 'zhTW', '你現在擁有一個公會。你可以購買公會會館！'),
(1, 'esES', 'Ahora eres dueño de una hermandad. ¡Puedes comprar una casa de hermandad!'),
(1, 'esMX', 'Ahora eres dueño de una hermandad. ¡Puedes comprar una casa de hermandad!'),
(1, 'ruRU', 'Теперь вы владеете гильдией. Вы можете приобрести дом гильдии!'),

-- 2: no guild
(2, 'enUS', 'You are not in a guild.'),
(2, 'frFR', 'Vous n''êtes pas dans une guilde.'),
(2, 'koKR', '당신은 길드에 속해 있지 않습니다.'),
(2, 'deDE', 'Du bist in keiner Gilde.'),
(2, 'zhCN', '你不在任何公会中。'),
(2, 'zhTW', '你目前沒有加入任何公會。'),
(2, 'esES', 'No estás en una hermandad.'),
(2, 'esMX', 'No estás en una hermandad.'),
(2, 'ruRU', 'Вы не состоите в гильдии.'),

-- 3: The guild does not have a guild house
(3, 'enUS', 'Your guild does not own a Guild House.'),
(3, 'frFR', 'Votre guilde ne possède pas de maison de guilde.'),
(3, 'koKR', '당신의 길드는 길드 하우스를 소유하고 있지 않습니다.'),
(3, 'deDE', 'Deine Gilde besitzt noch kein Gildenhaus.'),
(3, 'zhCN', '你的公会还没有公会大厅。'),
(3, 'zhTW', '你的公會尚未擁有公會會館。'),
(3, 'esES', 'Tu hermandad no posee una casa de hermandad.'),
(3, 'esMX', 'Tu hermandad no posee una casa de hermandad.'),
(3, 'ruRU', 'Ваша гильдия не владеет домом гильдии.'),

-- 4: Successful sale
(4, 'enUS', 'You have successfully sold your Guild House.'),
(4, 'frFR', 'Vous avez vendu votre maison de guilde avec succès.'),
(4, 'koKR', '길드 하우스를 성공적으로 판매했습니다.'),
(4, 'deDE', 'Du hast dein Gildenhaus erfolgreich verkauft.'),
(4, 'zhCN', '你已成功出售公会大厅。'),
(4, 'zhTW', '你已成功賣掉公會會館。'),
(4, 'esES', 'Has vendido tu casa de hermandad con éxito.'),
(4, 'esMX', 'Has vendido con éxito tu casa de hermandad.'),
(4, 'ruRU', 'Вы успешно продали дом гильдии.'),

-- 5: sales error
(5, 'enUS', 'There was an error selling your Guild House.'),
(5, 'frFR', 'Une erreur s''est produite lors de la vente de votre maison de guilde.'),
(5, 'koKR', '길드 하우스를 판매하는 동안 오류가 발생했습니다.'),
(5, 'deDE', 'Beim Verkauf deines Gildenhauses ist ein Fehler aufgetreten.'),
(5, 'zhCN', '出售公会大厅时发生错误。'),
(5, 'zhTW', '在出售公會會館時發生錯誤。'),
(5, 'esES', 'Se ha producido un error al vender tu casa de hermandad.'),
(5, 'esMX', 'Ocurrió un error al vender tu casa de hermandad.'),
(5, 'ruRU', 'Произошла ошибка при продаже дома гильдии.'),

-- 6: Successful purchase
(6, 'enUS', 'You have successfully purchased a Guild House.'),
(6, 'frFR', 'Vous avez acheté une maison de guilde avec succès.'),
(6, 'koKR', '길드 하우스를 성공적으로 구매했습니다.'),
(6, 'deDE', 'Du hast erfolgreich ein Gildenhaus gekauft.'),
(6, 'zhCN', '你已成功购买公会大厅。'),
(6, 'zhTW', '你已成功購買公會會館。'),
(6, 'esES', 'Has comprado una casa de hermandad con éxito.'),
(6, 'esMX', 'Has comprado con éxito una casa de hermandad.'),
(6, 'ruRU', 'Вы успешно приобрели дом гильдии.'),

-- 7: The guild already owns a house
(7, 'enUS', 'Your guild already has a Guild House.'),
(7, 'frFR', 'Votre guilde possède déjà une maison de guilde.'),
(7, 'koKR', '당신의 길드는 이미 길드 하우스를 소유하고 있습니다.'),
(7, 'deDE', 'Deine Gilde besitzt bereits ein Gildenhaus.'),
(7, 'zhCN', '你的公会已经拥有公会大厅。'),
(7, 'zhTW', '你的公會已經擁有公會會館。'),
(7, 'esES', 'Tu hermandad ya tiene una casa de hermandad.'),
(7, 'esMX', 'Tu hermandad ya tiene una casa de hermandad.'),
(7, 'ruRU', 'Ваша гильдия уже имеет дом гильдии.'),

-- 8: Command reserved for the guild master
(8, 'enUS', 'You must be the Guild Master of a guild to use this command!'),
(8, 'frFR', 'Vous devez être maître de guilde pour utiliser cette commande !'),
(8, 'koKR', '이 명령을 사용하려면 길드 마스터여야 합니다!'),
(8, 'deDE', 'Du musst Gildenmeister einer Gilde sein, um diesen Befehl zu verwenden!'),
(8, 'zhCN', '你必须是公会会长才能使用这个命令！'),
(8, 'zhTW', '你必須是公會會長才能使用這個指令！'),
(8, 'esES', '¡Debes ser el maestro de hermandad para usar este comando!'),
(8, 'esMX', '¡Debes ser el maestro de hermandad para usar este comando!'),
(8, 'ruRU', 'Вы должны быть гильдмастером, чтобы использовать эту команду!'),

-- 9: must be in the guild house
(9, 'enUS', 'You must be in your Guild House to use this command!'),
(9, 'frFR', 'Vous devez être dans votre maison de guilde pour utiliser cette commande !'),
(9, 'koKR', '이 명령을 사용하려면 길드 하우스 안에 있어야 합니다!'),
(9, 'deDE', 'Du musst dich in deinem Gildenhaus befinden, um diesen Befehl zu verwenden!'),
(9, 'zhCN', '你必须在你的公会大厅中才能使用这个命令！'),
(9, 'zhTW', '你必須在你的公會會館中才能使用這個指令！'),
(9, 'esES', '¡Debes estar en tu casa de hermandad para usar este comando!'),
(9, 'esMX', '¡Debes estar en tu casa de hermandad para usar este comando!'),
(9, 'ruRU', 'Вы должны находиться в доме гильдии, чтобы использовать эту команду!'),

-- 10: Butler already present
(10, 'enUS', 'You already have the Guild House Butler!'),
(10, 'frFR', 'Vous avez déjà le majordome de la maison de guilde !'),
(10, 'koKR', '이미 길드 하우스 집사가 있습니다!'),
(10, 'deDE', 'Du hast den Gildenhausdiener bereits!'),
(10, 'zhCN', '你已经拥有公会大厅管家了！'),
(10, 'zhTW', '你已經擁有公會會館管家了！'),
(10, 'esES', '¡Ya tienes el mayordomo de la casa de hermandad!'),
(10, 'esMX', '¡Ya tienes al mayordomo de la casa de hermandad!'),
(10, 'ruRU', 'У вас уже есть дворецкий дома гильдии!'),

-- 11: Butler added error
(11, 'enUS', 'Something went wrong when adding the Butler.'),
(11, 'frFR', 'Un problème est survenu lors de l''ajout du majordome.'),
(11, 'koKR', '집사를 추가하는 동안 문제가 발생했습니다.'),
(11, 'deDE', 'Beim Hinzufügen des Dieners ist etwas schiefgelaufen.'),
(11, 'zhCN', '添加管家时出现了一些问题。'),
(11, 'zhTW', '新增管家時發生了一些問題。'),
(11, 'esES', 'Algo salió mal al añadir al mayordomo.'),
(11, 'esMX', 'Algo salió mal al agregar al mayordomo.'),
(11, 'ruRU', 'При добавлении дворецкого что-то пошло не так.'),

-- 12: Combat command
(12, 'enUS', 'You can''t use this command while in combat!'),
(12, 'frFR', 'Vous ne pouvez pas utiliser cette commande en combat !'),
(12, 'koKR', '전투 중에는 이 명령을 사용할 수 없습니다!'),
(12, 'deDE', 'Du kannst diesen Befehl im Kampf nicht verwenden!'),
(12, 'zhCN', '战斗中不能使用这个命令！'),
(12, 'zhTW', '戰鬥中無法使用這個指令！'),
(12, 'esES', '¡No puedes usar este comando mientras estás en combate!'),
(12, 'esMX', '¡No puedes usar este comando mientras estás en combate!'),
(12, 'ruRU', 'Вы не можете использовать эту команду во время боя!'),

-- 20: broadcast sale
(20, 'enUS', 'We just sold our Guild House.'),
(20, 'frFR', 'Nous venons de vendre notre maison de guilde.'),
(20, 'koKR', '우리는 방금 길드 하우스를 팔았습니다.'),
(20, 'deDE', 'Wir haben gerade unser Gildenhaus verkauft.'),
(20, 'zhCN', '我们刚刚卖掉了我们的公会大厅。'),
(20, 'zhTW', '我們剛剛賣掉了我們的公會會館。'),
(20, 'esES', 'Acabamos de vender nuestra casa de hermandad.'),
(20, 'esMX', 'Acabamos de vender nuestra casa de hermandad.'),
(20, 'ruRU', 'Мы только что продали наш дом гильдии.'),

-- 21: broadcast purchase
(21, 'enUS', 'We now have a Guild House!'),
(21, 'frFR', 'Nous avons maintenant une maison de guilde !'),
(21, 'koKR', '이제 우리는 길드 하우스를 갖게 되었습니다!'),
(21, 'deDE', 'Wir haben jetzt ein Gildenhaus!'),
(21, 'zhCN', '我们现在拥有一座公会大厅！'),
(21, 'zhTW', '我們現在擁有一座公會會館！'),
(21, 'esES', '¡Ahora tenemos una casa de hermandad!'),
(21, 'esMX', '¡Ahora tenemos una casa de hermandad!'),
(21, 'ruRU', 'Теперь у нас есть дом гильдии!'),

-- 22: Broadcast recall of teleport commands
(22, 'enUS', 'You can use `.guildhouse tele` or `.gh tele` to visit the Guild House!'),
(22, 'frFR', 'Vous pouvez utiliser `.guildhouse tele` ou `.gh tele` pour visiter la maison de guilde !'),
(22, 'koKR', '`.guildhouse tele` 또는 `.gh tele`을 사용해서 길드 하우스로 이동할 수 있습니다!'),
(22, 'deDE', 'Ihr könnt `.guildhouse tele` oder `.gh tele` benutzen, um das Gildenhaus zu besuchen!'),
(22, 'zhCN', '你可以使用 `.guildhouse tele` 或 `.gh tele` 前往公会大厅！'),
(22, 'zhTW', '你可以使用 `.guildhouse tele` 或 `.gh tele` 前往公會會館！'),
(22, 'esES', '¡Puedes usar `.guildhouse tele` o `.gh tele` para visitar la casa de hermandad!'),
(22, 'esMX', '¡Puedes usar `.guildhouse tele` o `.gh tele` para visitar la casa de hermandad!'),
(22, 'ruRU', 'Вы можете использовать `.guildhouse tele` или `.gh tele`, чтобы посетить дом гильдии!'),

-- 30: not authorized to buy
(30, 'enUS', 'You are not authorized to make Guild House purchases.'),
(30, 'frFR', 'Vous n''êtes pas autorisé à faire des achats pour la maison de guilde.'),
(30, 'koKR', '당신은 길드 하우스 구매를 할 권한이 없습니다.'),
(30, 'deDE', 'Du bist nicht berechtigt, Einkäufe für das Gildenhaus zu tätigen.'),
(30, 'zhCN', '你没有权限为公会大厅进行购买。'),
(30, 'zhTW', '你沒有權限為公會會館進行購買。'),
(30, 'esES', 'No estás autorizado para realizar compras de la casa de hermandad.'),
(30, 'esMX', 'No estás autorizado para hacer compras para la casa de hermandad.'),
(30, 'ruRU', 'У вас нет прав совершать покупки для дома гильдии.'),

-- 31: object already present
(31, 'enUS', 'You already have this object!'),
(31, 'frFR', 'Vous avez déjà cet objet !'),
(31, 'koKR', '이미 이 오브젝트를 가지고 있습니다!'),
(31, 'deDE', 'Du besitzt dieses Objekt bereits!'),
(31, 'zhCN', '你已经拥有这个物体了！'),
(31, 'zhTW', '你已經擁有這個物品了！'),
(31, 'esES', '¡Ya tienes este objeto!'),
(31, 'esMX', '¡Ya tienes este objeto!'),
(31, 'ruRU', 'У вас уже есть этот объект!'),

-- 100: Gossip about buying a house
(100, 'enUS', 'Buy Guild House!'),
(100, 'frFR', 'Acheter une maison de guilde !'),
(100, 'koKR', '길드 하우스 구입!'),
(100, 'deDE', 'Gildenhaus kaufen!'),
(100, 'zhCN', '购买公会大厅！'),
(100, 'zhTW', '購買公會會館！'),
(100, 'esES', '¡Comprar casa de hermandad!'),
(100, 'esMX', '¡Comprar casa de hermandad!'),
(100, 'ruRU', 'Купить дом гильдии!'),

-- 101: Confirmation of selling house
(101, 'enUS', 'Are you sure you want to sell your Guild House?'),
(101, 'frFR', 'Êtes-vous sûr de vouloir vendre votre maison de guilde ?'),
(101, 'koKR', '정말 길드 하우스를 판매하시겠습니까?'),
(101, 'deDE', 'Bist du sicher, dass du dein Gildenhaus verkaufen möchtest?'),
(101, 'zhCN', '你确定要出售你的公会大厅吗？'),
(101, 'zhTW', '你確定要賣掉你的公會會館嗎？'),
(101, 'esES', '¿Seguro que quieres vender tu casa de hermandad?'),
(101, 'esMX', '¿Seguro que quieres vender tu casa de hermandad?'),
(101, 'ruRU', 'Вы уверены, что хотите продать дом гильдии?'),

-- 102: Teleportation to the house
(102, 'enUS', 'Teleport to Guild House'),
(102, 'frFR', 'Téléportation vers la maison de guilde'),
(102, 'koKR', '길드 하우스로 순간이동'),
(102, 'deDE', 'Zum Gildenhaus teleportieren'),
(102, 'zhCN', '传送到公会大厅'),
(102, 'zhTW', '傳送到公會會館'),
(102, 'esES', 'Teletransportarse a la casa de hermandad'),
(102, 'esMX', 'Teletransportarse a la casa de hermandad'),
(102, 'ruRU', 'Телепорт в дом гильдии'),

-- 103: Close the menu
(103, 'enUS', 'Close'),
(103, 'frFR', 'Fermer'),
(103, 'koKR', '닫기'),
(103, 'deDE', 'Schließen'),
(103, 'zhCN', '关闭'),
(103, 'zhTW', '關閉'),
(103, 'esES', 'Cerrar'),
(103, 'esMX', 'Cerrar'),
(103, 'ruRU', 'Закрыть'),

-- 104: label sell house
(104, 'enUS', 'Sell Guild House!'),
(104, 'frFR', 'Vendre la maison de guilde !'),
(104, 'koKR', '길드 하우스 판매!'),
(104, 'deDE', 'Gildenhaus verkaufen!'),
(104, 'zhCN', '出售公会大厅！'),
(104, 'zhTW', '賣掉公會會館！'),
(104, 'esES', '¡Vender la casa de hermandad!'),
(104, 'esMX', '¡Vender la casa de hermandad!'),
(104, 'ruRU', 'Продать дом гильдии!');


-- ============================================================================
-- 6. WORLD DB: 집사 메뉴/지역 선택 다국어 문자열 (재실행 가능)
-- ============================================================================
REPLACE INTO `mod_guildhouse_locale` (`Id`, `Locale`, `Text`) VALUES
-- 200–212 : main butler menu
(200, 'enUS', 'Spawn Innkeeper'),
(200, 'koKR', '여관주인 소환'),
(200, 'frFR', 'Invoquer un aubergiste'),
(200, 'deDE', 'Gastwirt beschwören'),
(200, 'zhCN', '生成旅店老板'),
(200, 'zhTW', '召喚旅店老闆'),
(200, 'esES', 'Invocar tabernero'),
(200, 'esMX', 'Invocar tabernero'),
(200, 'ruRU', 'Призвать трактирщика'),

(201, 'enUS', 'Spawn Mailbox'),
(201, 'koKR', '우편함 소환'),
(201, 'frFR', 'Invoquer une boîte aux lettres'),
(201, 'deDE', 'Briefkasten beschwören'),
(201, 'zhCN', '生成邮箱'),
(201, 'zhTW', '召喚郵箱'),
(201, 'esES', 'Invocar buzón'),
(201, 'esMX', 'Invocar buzón'),
(201, 'ruRU', 'Призвать почтовый ящик'),

(202, 'enUS', 'Spawn Stable Master'),
(202, 'koKR', '마구간지기 소환'),
(202, 'frFR', 'Invoquer un maître d''écurie'),
(202, 'deDE', 'Stallmeister beschwören'),
(202, 'zhCN', '生成兽栏管理员'),
(202, 'zhTW', '召喚獸欄管理員'),
(202, 'esES', 'Invocar maestro de establos'),
(202, 'esMX', 'Invocar maestro de establos'),
(202, 'ruRU', 'Призвать конюха'),

(203, 'enUS', 'Spawn Class Trainer'),
(203, 'koKR', '직업 교관 소환'),
(203, 'frFR', 'Invoquer un maître de classe'),
(203, 'deDE', 'Klassenausbilder beschwören'),
(203, 'zhCN', '生成职业训练师'),
(203, 'zhTW', '召喚職業訓練師'),
(203, 'esES', 'Invocar instructor de clase'),
(203, 'esMX', 'Invocar instructor de clase'),
(203, 'ruRU', 'Призвать наставника класса'),

(204, 'enUS', 'Spawn Vendor'),
(204, 'koKR', '상인 소환'),
(204, 'frFR', 'Invoquer un vendeur'),
(204, 'deDE', 'Händler beschwören'),
(204, 'zhCN', '生成商人'),
(204, 'zhTW', '召喚商人'),
(204, 'esES', 'Invocar vendedor'),
(204, 'esMX', 'Invocar vendedor'),
(204, 'ruRU', 'Призвать торговца'),

(205, 'enUS', 'Spawn City Portals / Objects'),
(205, 'koKR', '도시 차원문 / 오브젝트 소환'),
(205, 'frFR', 'Invoquer des portails / objets de ville'),
(205, 'deDE', 'Stadtportale / Objekte beschwören'),
(205, 'zhCN', '生成城市传送门/物件'),
(205, 'zhTW', '召喚城市傳送門/物件'),
(205, 'esES', 'Invocar portales / objetos de ciudad'),
(205, 'esMX', 'Invocar portales / objetos de ciudad'),
(205, 'ruRU', 'Призвать городские порталы/объекты'),

(206, 'enUS', 'Spawn Bank'),
(206, 'koKR', '은행원 소환'),
(206, 'frFR', 'Invoquer une banque'),
(206, 'deDE', 'Bankier beschwören'),
(206, 'zhCN', '生成银行职员'),
(206, 'zhTW', '召喚銀行職員'),
(206, 'esES', 'Invocar banquero'),
(206, 'esMX', 'Invocar banquero'),
(206, 'ruRU', 'Призвать банкира'),

(207, 'enUS', 'Spawn Auctioneer'),
(207, 'koKR', '경매인 소환'),
(207, 'frFR', 'Invoquer un commissaire-priseur'),
(207, 'deDE', 'Auktionator beschwören'),
(207, 'zhCN', '生成拍卖师'),
(207, 'zhTW', '召喚拍賣師'),
(207, 'esES', 'Invocar subastador'),
(207, 'esMX', 'Invocar subastador'),
(207, 'ruRU', 'Призвать аукциониста'),

(208, 'enUS', 'Spawn Neutral Auctioneer'),
(208, 'koKR', '중립 경매인 소환'),
(208, 'frFR', 'Invoquer un commissaire-priseur neutre'),
(208, 'deDE', 'Neutralen Auktionator beschwören'),
(208, 'zhCN', '生成中立拍卖师'),
(208, 'zhTW', '召喚中立拍賣師'),
(208, 'esES', 'Invocar subastador neutral'),
(208, 'esMX', 'Invocar subastador neutral'),
(208, 'ruRU', 'Призвать нейтрального аукциониста'),

(209, 'enUS', 'Spawn Primary Profession Trainers'),
(209, 'koKR', '주 전문기술 조언가 소환'),
(209, 'frFR', 'Invoquer les maîtres de professions principales'),
(209, 'deDE', 'Lehrer für Hauptberufe beschwören'),
(209, 'zhCN', '生成主专业训练师'),
(209, 'zhTW', '召喚主要專業技能訓練師'),
(209, 'esES', 'Invocar instructores de profesiones primarias'),
(209, 'esMX', 'Invocar instructores de profesiones primarias'),
(209, 'ruRU', 'Призвать наставников основных профессий'),

(210, 'enUS', 'Spawn Secondary Profession Trainers'),
(210, 'koKR', '보조 전문기술 조언가 소환'),
(210, 'frFR', 'Invoquer les maîtres de professions secondaires'),
(210, 'deDE', 'Lehrer für Nebenberufe beschwören'),
(210, 'zhCN', '生成辅助专业训练师'),
(210, 'zhTW', '召喚次要專業技能訓練師'),
(210, 'esES', 'Invocar instructores de profesiones secundarias'),
(210, 'esMX', 'Invocar instructores de profesiones secundarias'),
(210, 'ruRU', 'Призвать наставников вторичных профессий'),

(211, 'enUS', 'Spawn Spirit Healer'),
(211, 'koKR', '영혼의 치유사 소환'),
(211, 'frFR', 'Invoquer un gardien des esprits'),
(211, 'deDE', 'Geistheilerin beschwören'),
(211, 'zhCN', '生成灵魂医者'),
(211, 'zhTW', '召喚靈魂醫者'),
(211, 'esES', 'Invocar espíritu sanador'),
(211, 'esMX', 'Invocar espíritu sanador'),
(211, 'ruRU', 'Призвать целителя душ'),

(212, 'enUS', 'Go Back!'),
(212, 'koKR', '돌아가기'),
(212, 'frFR', 'Retour'),
(212, 'deDE', 'Zurück!'),
(212, 'zhCN', '返回'),
(212, 'zhTW', '返回'),
(212, 'esES', 'Volver'),
(212, 'esMX', 'Volver'),
(212, 'ruRU', 'Назад'),

-- 213–219 : main butler confirmations
(213, 'enUS', 'Spawn Innkeeper?'),
(213, 'koKR', '여관주인을 소환하시겠습니까?'),
(213, 'frFR', 'Invoquer un aubergiste ?'),
(213, 'deDE', 'Gastwirt beschwören?'),
(213, 'zhCN', '生成旅店老板？'),
(213, 'zhTW', '召喚旅店老闆？'),
(213, 'esES', '¿Invocar tabernero?'),
(213, 'esMX', '¿Invocar tabernero?'),
(213, 'ruRU', 'Призвать трактирщика?'),

(214, 'enUS', 'Spawn Mailbox?'),
(214, 'koKR', '우편함을 소환하시겠습니까?'),
(214, 'frFR', 'Invoquer une boîte aux lettres ?'),
(214, 'deDE', 'Briefkasten beschwören?'),
(214, 'zhCN', '生成邮箱？'),
(214, 'zhTW', '召喚郵箱？'),
(214, 'esES', '¿Invocar buzón?'),
(214, 'esMX', '¿Invocar buzón?'),
(214, 'ruRU', 'Призвать почтовый ящик?'),

(215, 'enUS', 'Spawn Stable Master?'),
(215, 'koKR', '마구간지기를 소환하시겠습니까?'),
(215, 'frFR', 'Invoquer un maître d''écurie ?'),
(215, 'deDE', 'Stallmeister beschwören?'),
(215, 'zhCN', '生成兽栏管理员？'),
(215, 'zhTW', '召喚獸欄管理員？'),
(215, 'esES', '¿Invocar maestro de establos?'),
(215, 'esMX', '¿Invocar maestro de establos?'),
(215, 'ruRU', 'Призвать конюха?'),

(216, 'enUS', 'Spawn Banker?'),
(216, 'koKR', '은행원을 소환하시겠습니까?'),
(216, 'frFR', 'Invoquer un banquier ?'),
(216, 'deDE', 'Bankier beschwören?'),
(216, 'zhCN', '生成银行职员？'),
(216, 'zhTW', '召喚銀行職員？'),
(216, 'esES', '¿Invocar banquero?'),
(216, 'esMX', '¿Invocar banquero?'),
(216, 'ruRU', 'Призвать банкира?'),

(217, 'enUS', 'Spawn Auctioneer?'),
(217, 'koKR', '경매인을 소환하시겠습니까?'),
(217, 'frFR', 'Invoquer un commissaire-priseur ?'),
(217, 'deDE', 'Auktionator beschwören?'),
(217, 'zhCN', '生成拍卖师？'),
(217, 'zhTW', '召喚拍賣師？'),
(217, 'esES', '¿Invocar subastador?'),
(217, 'esMX', '¿Invocar subastador?'),
(217, 'ruRU', 'Призвать аукциониста?'),

(218, 'enUS', 'Spawn Neutral Auctioneer?'),
(218, 'koKR', '중립 경매인을 소환하시겠습니까?'),
(218, 'frFR', 'Invoquer un commissaire-priseur neutre ?'),
(218, 'deDE', 'Neutralen Auktionator beschwören?'),
(218, 'zhCN', '生成中立拍卖师？'),
(218, 'zhTW', '召喚中立拍賣師？'),
(218, 'esES', '¿Invocar subastador neutral?'),
(218, 'esMX', '¿Invocar subastador neutral?'),
(218, 'ruRU', 'Призвать нейтрального аукциониста?'),

(219, 'enUS', 'Spawn Spirit Healer?'),
(219, 'koKR', '영혼의 치유사를 소환하시겠습니까?'),
(219, 'frFR', 'Invoquer un gardien des esprits ?'),
(219, 'deDE', 'Geistheilerin beschwören?'),
(219, 'zhCN', '生成灵魂医者？'),
(219, 'zhTW', '召喚靈魂醫者？'),
(219, 'esES', '¿Invocar espíritu sanador?'),
(219, 'esMX', '¿Invocar espíritu sanador?'),
(219, 'ruRU', 'Призвать целителя душ?'),

-- 220–229 : class trainer labels
(220, 'enUS', 'Death Knight'),
(220, 'koKR', '죽음의 기사'),
(220, 'frFR', 'Chevalier de la mort'),
(220, 'deDE', 'Todesritter'),
(220, 'zhCN', '死亡骑士'),
(220, 'zhTW', '死亡騎士'),
(220, 'esES', 'Caballero de la Muerte'),
(220, 'esMX', 'Caballero de la Muerte'),
(220, 'ruRU', 'Рыцарь смерти'),

(221, 'enUS', 'Druid'),
(221, 'koKR', '드루이드'),
(221, 'frFR', 'Druide'),
(221, 'deDE', 'Druide'),
(221, 'zhCN', '德鲁伊'),
(221, 'zhTW', '德魯伊'),
(221, 'esES', 'Druida'),
(221, 'esMX', 'Druida'),
(221, 'ruRU', 'Друид'),

(222, 'enUS', 'Hunter'),
(222, 'koKR', '사냥꾼'),
(222, 'frFR', 'Chasseur'),
(222, 'deDE', 'Jäger'),
(222, 'zhCN', '猎人'),
(222, 'zhTW', '獵人'),
(222, 'esES', 'Cazador'),
(222, 'esMX', 'Cazador'),
(222, 'ruRU', 'Охотник'),

(223, 'enUS', 'Mage'),
(223, 'koKR', '마법사'),
(223, 'frFR', 'Mage'),
(223, 'deDE', 'Magier'),
(223, 'zhCN', '法师'),
(223, 'zhTW', '法師'),
(223, 'esES', 'Mago'),
(223, 'esMX', 'Mago'),
(223, 'ruRU', 'Маг'),

(224, 'enUS', 'Paladin'),
(224, 'koKR', '성기사'),
(224, 'frFR', 'Paladin'),
(224, 'deDE', 'Paladin'),
(224, 'zhCN', '圣骑士'),
(224, 'zhTW', '聖騎士'),
(224, 'esES', 'Paladín'),
(224, 'esMX', 'Paladín'),
(224, 'ruRU', 'Паладин'),

(225, 'enUS', 'Priest'),
(225, 'koKR', '사제'),
(225, 'frFR', 'Prêtre'),
(225, 'deDE', 'Priester'),
(225, 'zhCN', '牧师'),
(225, 'zhTW', '牧師'),
(225, 'esES', 'Sacerdote'),
(225, 'esMX', 'Sacerdote'),
(225, 'ruRU', 'Жрец'),

(226, 'enUS', 'Rogue'),
(226, 'koKR', '도적'),
(226, 'frFR', 'Voleur'),
(226, 'deDE', 'Schurke'),
(226, 'zhCN', '潜行者'),
(226, 'zhTW', '盜賊'),
(226, 'esES', 'Pícaro'),
(226, 'esMX', 'Pícaro'),
(226, 'ruRU', 'Разбойник'),

(227, 'enUS', 'Shaman'),
(227, 'koKR', '주술사'),
(227, 'frFR', 'Chaman'),
(227, 'deDE', 'Schamane'),
(227, 'zhCN', '萨满祭司'),
(227, 'zhTW', '薩滿'),
(227, 'esES', 'Chamán'),
(227, 'esMX', 'Chamán'),
(227, 'ruRU', 'Шаман'),

(228, 'enUS', 'Warlock'),
(228, 'koKR', '흑마법사'),
(228, 'frFR', 'Démoniste'),
(228, 'deDE', 'Hexenmeister'),
(228, 'zhCN', '术士'),
(228, 'zhTW', '術士'),
(228, 'esES', 'Brujo'),
(228, 'esMX', 'Brujo'),
(228, 'ruRU', 'Чернокнижник'),

(229, 'enUS', 'Warrior'),
(229, 'koKR', '전사'),
(229, 'frFR', 'Guerrier'),
(229, 'deDE', 'Krieger'),
(229, 'zhCN', '战士'),
(229, 'zhTW', '戰士'),
(229, 'esES', 'Guerrero'),
(229, 'esMX', 'Guerrero'),
(229, 'ruRU', 'Воин'),

-- 230–239 : class trainer confirmations
(230, 'enUS', 'Spawn Death Knight Trainer?'),
(230, 'koKR', '죽음의 기사 교관을 소환하시겠습니까?'),
(230, 'frFR', 'Invoquer un maître de chevalier de la mort ?'),
(230, 'deDE', 'Todesritterlehrer beschwören?'),
(230, 'zhCN', '生成死亡骑士训练师？'),
(230, 'zhTW', '召喚死亡騎士訓練師？'),
(230, 'esES', '¿Invocar instructor de caballeros de la Muerte?'),
(230, 'esMX', '¿Invocar instructor de caballeros de la Muerte?'),
(230, 'ruRU', 'Призвать наставника рыцарей смерти?'),

(231, 'enUS', 'Spawn Druid Trainer?'),
(231, 'koKR', '드루이드 교관을 소환하시겠습니까?'),
(231, 'frFR', 'Invoquer un maître druide ?'),
(231, 'deDE', 'Druidenlehrer beschwören?'),
(231, 'zhCN', '生成德鲁伊训练师？'),
(231, 'zhTW', '召喚德魯伊訓練師？'),
(231, 'esES', '¿Invocar instructor de druidas?'),
(231, 'esMX', '¿Invocar instructor de druidas?'),
(231, 'ruRU', 'Призвать наставника друидов?'),

(232, 'enUS', 'Spawn Hunter Trainer?'),
(232, 'koKR', '사냥꾼 교관을 소환하시겠습니까?'),
(232, 'frFR', 'Invoquer un maître chasseur ?'),
(232, 'deDE', 'Jägerlehrer beschwören?'),
(232, 'zhCN', '生成猎人训练师？'),
(232, 'zhTW', '召喚獵人訓練師？'),
(232, 'esES', '¿Invocar instructor de cazadores?'),
(232, 'esMX', '¿Invocar instructor de cazadores?'),
(232, 'ruRU', 'Призвать наставника охотников?'),

(233, 'enUS', 'Spawn Mage Trainer?'),
(233, 'koKR', '마법사 교관을 소환하시겠습니까?'),
(233, 'frFR', 'Invoquer un maître mage ?'),
(233, 'deDE', 'Magielehrer beschwören?'),
(233, 'zhCN', '生成法师训练师？'),
(233, 'zhTW', '召喚法師訓練師？'),
(233, 'esES', '¿Invocar instructor de magos?'),
(233, 'esMX', '¿Invocar instructor de magos?'),
(233, 'ruRU', 'Призвать наставника магов?'),

(234, 'enUS', 'Spawn Paladin Trainer?'),
(234, 'koKR', '성기사 교관을 소환하시겠습니까?'),
(234, 'frFR', 'Invoquer un maître paladin ?'),
(234, 'deDE', 'Paladinlehrer beschwören?'),
(234, 'zhCN', '生成圣骑士训练师？'),
(234, 'zhTW', '召喚聖騎士訓練師？'),
(234, 'esES', '¿Invocar instructor de paladines?'),
(234, 'esMX', '¿Invocar instructor de paladines?'),
(234, 'ruRU', 'Призвать наставника паладинов?'),

(235, 'enUS', 'Spawn Priest Trainer?'),
(235, 'koKR', '사제 교관을 소환하시겠습니까?'),
(235, 'frFR', 'Invoquer un maître prêtre ?'),
(235, 'deDE', 'Priesterlehrer beschwören?'),
(235, 'zhCN', '生成牧师训练师？'),
(235, 'zhTW', '召喚牧師訓練師？'),
(235, 'esES', '¿Invocar instructor de sacerdotes?'),
(235, 'esMX', '¿Invocar instructor de sacerdotes?'),
(235, 'ruRU', 'Призвать наставника жрецов?'),

(236, 'enUS', 'Spawn Rogue Trainer?'),
(236, 'koKR', '도적 교관을 소환하시겠습니까?'),
(236, 'frFR', 'Invoquer un maître voleur ?'),
(236, 'deDE', 'Schurkenlehrer beschwören?'),
(236, 'zhCN', '生成潜行者训练师？'),
(236, 'zhTW', '召喚盜賊訓練師？'),
(236, 'esES', '¿Invocar instructor de pícaros?'),
(236, 'esMX', '¿Invocar instructor de pícaros?'),
(236, 'ruRU', 'Призвать наставника разбойников?'),

(237, 'enUS', 'Spawn Shaman Trainer?'),
(237, 'koKR', '주술사 교관을 소환하시겠습니까?'),
(237, 'frFR', 'Invoquer un maître chaman ?'),
(237, 'deDE', 'Schamanenlehrer beschwören?'),
(237, 'zhCN', '生成萨满祭司训练师？'),
(237, 'zhTW', '召喚薩滿訓練師？'),
(237, 'esES', '¿Invocar instructor de chamanes?'),
(237, 'esMX', '¿Invocar instructor de chamanes?'),
(237, 'ruRU', 'Призвать наставника шаманов?'),

(238, 'enUS', 'Spawn Warlock Trainer?'),
(238, 'koKR', '흑마법사 교관을 소환하시겠습니까?'),
(238, 'frFR', 'Invoquer un maître démoniste ?'),
(238, 'deDE', 'Hexenmeisterlehrer beschwören?'),
(238, 'zhCN', '生成术士训练师？'),
(238, 'zhTW', '召喚術士訓練師？'),
(238, 'esES', '¿Invocar instructor de brujos?'),
(238, 'esMX', '¿Invocar instructor de brujos?'),
(238, 'ruRU', 'Призвать наставника чернокнижников?'),

(239, 'enUS', 'Spawn Warrior Trainer?'),
(239, 'koKR', '전사 교관을 소환하시겠습니까?'),
(239, 'frFR', 'Invoquer un maître guerrier ?'),
(239, 'deDE', 'Kriegerlehrer beschwören?'),
(239, 'zhCN', '生成战士训练师？'),
(239, 'zhTW', '召喚戰士訓練師？'),
(239, 'esES', '¿Invocar instructor de guerreros?'),
(239, 'esMX', '¿Invocar instructor de guerreros?'),
(239, 'ruRU', 'Призвать наставника воинов?'),

-- 300–305 : vendor submenu labels
(300, 'enUS', 'Trade Supplies'),
(300, 'koKR', '일반 용품 상인'),
(300, 'frFR', 'Fournitures commerciales'),
(300, 'deDE', 'Handelswaren'),
(300, 'zhCN', '杂货商'),
(300, 'zhTW', '雜貨商'),
(300, 'esES', 'Suministros comerciales'),
(300, 'esMX', 'Suministros comerciales'),
(300, 'ruRU', 'Торговые припасы'),

(301, 'enUS', 'Tabard Vendor'),
(301, 'koKR', '휘장 상인'),
(301, 'frFR', 'Vendeur de tabards'),
(301, 'deDE', 'Wappenrockverkäufer'),
(301, 'zhCN', '战袍商人'),
(301, 'zhTW', '戰袍商人'),
(301, 'esES', 'Vendedor de tabardos'),
(301, 'esMX', 'Vendedor de tabardos'),
(301, 'ruRU', 'Торговец гербовыми накидками'),

(302, 'enUS', 'Food & Drink Vendor'),
(302, 'koKR', '음식 및 음료 상인'),
(302, 'frFR', 'Vendeur de nourriture et boisson'),
(302, 'deDE', 'Nahrungs- & Getränkehändler'),
(302, 'zhCN', '食物和饮料商人'),
(302, 'zhTW', '食物與飲料商人'),
(302, 'esES', 'Vendedor de comida y bebida'),
(302, 'esMX', 'Vendedor de comida y bebida'),
(302, 'ruRU', 'Торговец едой и напитками'),

(303, 'enUS', 'Reagent Vendor'),
(303, 'koKR', '재료 상인'),
(303, 'frFR', 'Vendeur de composants'),
(303, 'deDE', 'Reagenzienhändler'),
(303, 'zhCN', '施法材料商人'),
(303, 'zhTW', '施法材料商人'),
(303, 'esES', 'Vendedor de componentes'),
(303, 'esMX', 'Vendedor de componentes'),
(303, 'ruRU', 'Торговец реагентами'),

(304, 'enUS', 'Ammo & Repair Vendor'),
(304, 'koKR', '탄약 및 수리 상인'),
(304, 'frFR', 'Vendeur de munitions et réparation'),
(304, 'deDE', 'Händler für Munition & Reparaturen'),
(304, 'zhCN', '弹药与修理商人'),
(304, 'zhTW', '彈藥與修理商人'),
(304, 'esES', 'Vendedor de munición y reparación'),
(304, 'esMX', 'Vendedor de munición y reparación'),
(304, 'ruRU', 'Торговец боеприпасами и ремонтом'),

(305, 'enUS', 'Poisons Vendor'),
(305, 'koKR', '독 상인'),
(305, 'frFR', 'Vendeur de poisons'),
(305, 'deDE', 'Giftverkäufer'),
(305, 'zhCN', '毒药商人'),
(305, 'zhTW', '毒藥商人'),
(305, 'esES', 'Vendedor de venenos'),
(305, 'esMX', 'Vendedor de venenos'),
(305, 'ruRU', 'Торговец ядами'),

-- 310–315 : vendor submenu confirmations
(310, 'enUS', 'Spawn Trade Supplies?'),
(310, 'koKR', '일반 용품 상인을 소환하시겠습니까?'),
(310, 'frFR', 'Invoquer un marchand de fournitures commerciales ?'),
(310, 'deDE', 'Händler für Handelswaren beschwören?'),
(310, 'zhCN', '生成杂货商？'),
(310, 'zhTW', '召喚雜貨商？'),
(310, 'esES', '¿Invocar suministros comerciales?'),
(310, 'esMX', '¿Invocar suministros comerciales?'),
(310, 'ruRU', 'Призвать торговца припасами?'),

(311, 'enUS', 'Spawn Tabard Vendor?'),
(311, 'koKR', '휘장 상인을 소환하시겠습니까?'),
(311, 'frFR', 'Invoquer un vendeur de tabards ?'),
(311, 'deDE', 'Wappenrockverkäufer beschwören?'),
(311, 'zhCN', '生成战袍商人？'),
(311, 'zhTW', '召喚戰袍商人？'),
(311, 'esES', '¿Invocar vendedor de tabardos?'),
(311, 'esMX', '¿Invocar vendedor de tabardos?'),
(311, 'ruRU', 'Призвать торговца гербовыми накидками?'),

(312, 'enUS', 'Spawn Food & Drink Vendor?'),
(312, 'koKR', '음식 및 음료 상인을 소환하시겠습니까?'),
(312, 'frFR', 'Invoquer un vendeur de nourriture et boisson ?'),
(312, 'deDE', 'Nahrungs- & Getränkehändler beschwören?'),
(312, 'zhCN', '生成食物和饮料商人？'),
(312, 'zhTW', '召喚食物與飲料商人？'),
(312, 'esES', '¿Invocar vendedor de comida y bebida?'),
(312, 'esMX', '¿Invocar vendedor de comida y bebida?'),
(312, 'ruRU', 'Призвать торговца едой и напитками?'),

(313, 'enUS', 'Spawn Reagent Vendor?'),
(313, 'koKR', '재료 상인을 소환하시겠습니까?'),
(313, 'frFR', 'Invoquer un vendeur de composants ?'),
(313, 'deDE', 'Reagenzienhändler beschwören?'),
(313, 'zhCN', '生成施法材料商人？'),
(313, 'zhTW', '召喚施法材料商人？'),
(313, 'esES', '¿Invocar vendedor de componentes?'),
(313, 'esMX', '¿Invocar vendedor de componentes?'),
(313, 'ruRU', 'Призвать торговца реагентами?'),

(314, 'enUS', 'Spawn Ammo & Repair Vendor?'),
(314, 'koKR', '탄약 및 수리 상인을 소환하시겠습니까?'),
(314, 'frFR', 'Invoquer un vendeur de munitions et réparation ?'),
(314, 'deDE', 'Händler für Munition & Reparaturen beschwören?'),
(314, 'zhCN', '生成弹药与修理商人？'),
(314, 'zhTW', '召喚彈藥與修理商人？'),
(314, 'esES', '¿Invocar vendedor de munición y reparación?'),
(314, 'esMX', '¿Invocar vendedor de munición y reparación?'),
(314, 'ruRU', 'Призвать торговца боеприпасами и ремонтом?'),

(315, 'enUS', 'Spawn Poisons Vendor?'),
(315, 'koKR', '독 상인을 소환하시겠습니까?'),
(315, 'frFR', 'Invoquer un vendeur de poisons ?'),
(315, 'deDE', 'Giftverkäufer beschwören?'),
(315, 'zhCN', '生成毒药商人？'),
(315, 'zhTW', '召喚毒藥商人？'),
(315, 'esES', '¿Invocar vendedor de venenos?'),
(315, 'esMX', '¿Invocar vendedor de venenos?'),
(315, 'ruRU', 'Призвать торговца ядами?'),

-- 320–323 : objets
(320, 'enUS', 'Forge'),
(320, 'koKR', '용광로'),
(320, 'frFR', 'Forge'),
(320, 'deDE', 'Schmiede'),
(320, 'zhCN', '熔炉'),
(320, 'zhTW', '熔爐'),
(320, 'esES', 'Forja'),
(320, 'esMX', 'Forja'),
(320, 'ruRU', 'Горн'),

(321, 'enUS', 'Anvil'),
(321, 'koKR', '모루'),
(321, 'frFR', 'Enclume'),
(321, 'deDE', 'Amboss'),
(321, 'zhCN', '铁砧'),
(321, 'zhTW', '鐵砧'),
(321, 'esES', 'Yunque'),
(321, 'esMX', 'Yunque'),
(321, 'ruRU', 'Наковальня'),

(322, 'enUS', 'Guild Vault'),
(322, 'koKR', '길드 금고'),
(322, 'frFR', 'Coffre de guilde'),
(322, 'deDE', 'Gildenbank'),
(322, 'zhCN', '公会仓库'),
(322, 'zhTW', '公會保險箱'),
(322, 'esES', 'Bóveda de hermandad'),
(322, 'esMX', 'Bóveda de hermandad'),
(322, 'ruRU', 'Банк гильдии'),

(323, 'enUS', 'Barber Chair'),
(323, 'koKR', '이발 의자'),
(323, 'frFR', 'Fauteuil de barbier'),
(323, 'deDE', 'Barbiersitz'),
(323, 'zhCN', '理发椅'),
(323, 'zhTW', '理髮椅'),
(323, 'esES', 'Silla de barbero'),
(323, 'esMX', 'Silla de barbero'),
(323, 'ruRU', 'Парикмахерское кресло'),

-- 324–331 : labels des portails
(324, 'enUS', 'Portal: Ironforge'),
(324, 'koKR', '차원문: 아이언포지'),
(324, 'frFR', 'Portail : Forgefer'),
(324, 'deDE', 'Portal: Eisenschmiede'),
(324, 'zhCN', '传送门：铁炉堡'),
(324, 'zhTW', '傳送門：鐵爐堡'),
(324, 'esES', 'Portal: Forjaz'),
(324, 'esMX', 'Portal: Forjaz'),
(324, 'ruRU', 'Портал: Стальгорн'),

(325, 'enUS', 'Portal: Darnassus'),
(325, 'koKR', '차원문: 다르나서스'),
(325, 'frFR', 'Portail : Darnassus'),
(325, 'deDE', 'Portal: Darnassus'),
(325, 'zhCN', '传送门：达纳苏斯'),
(325, 'zhTW', '傳送門：達納蘇斯'),
(325, 'esES', 'Portal: Darnassus'),
(325, 'esMX', 'Portal: Darnassus'),
(325, 'ruRU', 'Портал: Дарнас'),

(326, 'enUS', 'Portal: Exodar'),
(326, 'koKR', '차원문: 엑소다르'),
(326, 'frFR', 'Portail : Exodar'),
(326, 'deDE', 'Portal: Exodar'),
(326, 'zhCN', '传送门：埃索达'),
(326, 'zhTW', '傳送門：艾克索達'),
(326, 'esES', 'Portal: Exodar'),
(326, 'esMX', 'Portal: Exodar'),
(326, 'ruRU', 'Портал: Экзодар'),

(327, 'enUS', 'Portal: Undercity'),
(327, 'koKR', '차원문: 언더시티'),
(327, 'frFR', 'Portail : Fossoyeuse'),
(327, 'deDE', 'Portal: Unterstadt'),
(327, 'zhCN', '传送门：幽暗城'),
(327, 'zhTW', '傳送門：幽暗城'),
(327, 'esES', 'Portal: Entrañas'),
(327, 'esMX', 'Portal: Entrañas'),
(327, 'ruRU', 'Портал: Подгород'),

(328, 'enUS', 'Portal: Thunderbluff'),
(328, 'koKR', '차원문: 썬더 블러프'),
(328, 'frFR', 'Portail : Les Pitons-du-Tonnerre'),
(328, 'deDE', 'Portal: Donnerfels'),
(328, 'zhCN', '传送门：雷霆崖'),
(328, 'zhTW', '傳送門：雷霆崖'),
(328, 'esES', 'Portal: Cima del Trueno'),
(328, 'esMX', 'Portal: Cima del Trueno'),
(328, 'ruRU', 'Портал: Громовой Утес'),

(329, 'enUS', 'Portal: Silvermoon'),
(329, 'koKR', '차원문: 실버문'),
(329, 'frFR', 'Portail : Lune-d’argent'),
(329, 'deDE', 'Portal: Silbermond'),
(329, 'zhCN', '传送门：银月城'),
(329, 'zhTW', '傳送門：銀月城'),
(329, 'esES', 'Portal: Lunargenta'),
(329, 'esMX', 'Portal: Lunargenta'),
(329, 'ruRU', 'Портал: Луносвет'),

(330, 'enUS', 'Portal: Shattrath'),
(330, 'koKR', '차원문: 샤트라스'),
(330, 'frFR', 'Portail : Shattrath'),
(330, 'deDE', 'Portal: Shattrath'),
(330, 'zhCN', '传送门：沙塔斯'),
(330, 'zhTW', '傳送門：撒塔斯'),
(330, 'esES', 'Portal: Shattrath'),
(330, 'esMX', 'Portal: Shattrath'),
(330, 'ruRU', 'Портал: Шаттрат'),

(331, 'enUS', 'Portal: Dalaran'),
(331, 'koKR', '차원문: 달라란'),
(331, 'frFR', 'Portail : Dalaran'),
(331, 'deDE', 'Portal: Dalaran'),
(331, 'zhCN', '传送门：达拉然'),
(331, 'zhTW', '傳送門：達拉然'),
(331, 'esES', 'Portal: Dalaran'),
(331, 'esMX', 'Portal: Dalaran'),
(331, 'ruRU', 'Портал: Даларан'),

-- 340–351 : confirmations objets / portails
(340, 'enUS', 'Add a Forge?'),
(340, 'koKR', '용광로를 추가하시겠습니까?'),
(340, 'frFR', 'Ajouter une forge ?'),
(340, 'deDE', 'Eine Schmiede hinzufügen?'),
(340, 'zhCN', '添加一座熔炉？'),
(340, 'zhTW', '新增一座熔爐？'),
(340, 'esES', '¿Añadir una forja?'),
(340, 'esMX', '¿Añadir una forja?'),
(340, 'ruRU', 'Добавить горн?'),

(341, 'enUS', 'Add an Anvil?'),
(341, 'koKR', '모루를 추가하시겠습니까?'),
(341, 'frFR', 'Ajouter une enclume ?'),
(341, 'deDE', 'Einen Amboss hinzufügen?'),
(341, 'zhCN', '添加一座铁砧？'),
(341, 'zhTW', '新增一座鐵砧？'),
(341, 'esES', '¿Añadir un yunque?'),
(341, 'esMX', '¿Añadir un yunque?'),
(341, 'ruRU', 'Добавить наковальню?'),

(342, 'enUS', 'Add Guild Vault?'),
(342, 'koKR', '길드 금고를 추가하시겠습니까?'),
(342, 'frFR', 'Ajouter un coffre de guilde ?'),
(342, 'deDE', 'Gildenbank hinzufügen?'),
(342, 'zhCN', '添加公会仓库？'),
(342, 'zhTW', '新增公會保險箱？'),
(342, 'esES', '¿Añadir bóveda de hermandad?'),
(342, 'esMX', '¿Añadir bóveda de hermandad?'),
(342, 'ruRU', 'Добавить банк гильдии?'),

(343, 'enUS', 'Add a Barber Chair?'),
(343, 'koKR', '이발 의자를 추가하시겠습니까?'),
(343, 'frFR', 'Ajouter un fauteuil de barbier ?'),
(343, 'deDE', 'Barbiersitz hinzufügen?'),
(343, 'zhCN', '添加一把理发椅？'),
(343, 'zhTW', '新增一把理髮椅？'),
(343, 'esES', '¿Añadir una silla de barbero?'),
(343, 'esMX', '¿Añadir una silla de barbero?'),
(343, 'ruRU', 'Добавить парикмахерское кресло?'),

(344, 'enUS', 'Add Ironforge Portal?'),
(344, 'koKR', '아이언포지 차원문을 추가하시겠습니까?'),
(344, 'frFR', 'Ajouter un portail pour Forgefer ?'),
(344, 'deDE', 'Portal nach Eisenschmiede hinzufügen?'),
(344, 'zhCN', '添加通往铁炉堡的传送门？'),
(344, 'zhTW', '新增通往鐵爐堡的傳送門？'),
(344, 'esES', '¿Añadir un portal a Forjaz?'),
(344, 'esMX', '¿Añadir un portal a Forjaz?'),
(344, 'ruRU', 'Добавить портал в Стальгорн?'),

(345, 'enUS', 'Add Darnassus Portal?'),
(345, 'koKR', '다르나서스 차원문을 추가하시겠습니까?'),
(345, 'frFR', 'Ajouter un portail pour Darnassus ?'),
(345, 'deDE', 'Portal nach Darnassus hinzufügen?'),
(345, 'zhCN', '添加通往达纳苏斯的传送门？'),
(345, 'zhTW', '新增通往達納蘇斯的傳送門？'),
(345, 'esES', '¿Añadir un portal a Darnassus?'),
(345, 'esMX', '¿Añadir un portal a Darnassus?'),
(345, 'ruRU', 'Добавить портал в Дарнас?'),

(346, 'enUS', 'Add Exodar Portal?'),
(346, 'koKR', '엑소다르 차원문을 추가하시겠습니까?'),
(346, 'frFR', 'Ajouter un portail pour Exodar ?'),
(346, 'deDE', 'Portal nach Exodar hinzufügen?'),
(346, 'zhCN', '添加通往埃索达的传送门？'),
(346, 'zhTW', '新增通往艾克索達的傳送門？'),
(346, 'esES', '¿Añadir un portal a Exodar?'),
(346, 'esMX', '¿Añadir un portal a Exodar?'),
(346, 'ruRU', 'Добавить портал в Экзодар?'),

(347, 'enUS', 'Add Undercity Portal?'),
(347, 'koKR', '언더시티 차원문을 추가하시겠습니까?'),
(347, 'frFR', 'Ajouter un portail pour Fossoyeuse ?'),
(347, 'deDE', 'Portal nach Unterstadt hinzufügen?'),
(347, 'zhCN', '添加通往幽暗城的传送门？'),
(347, 'zhTW', '新增通往幽暗城的傳送門？'),
(347, 'esES', '¿Añadir un portal a Entrañas?'),
(347, 'esMX', '¿Añadir un portal a Entrañas?'),
(347, 'ruRU', 'Добавить портал в Подгород?'),

(348, 'enUS', 'Add Thunderbluff Portal?'),
(348, 'koKR', '썬더 블러프 차원문을 추가하시겠습니까?'),
(348, 'frFR', 'Ajouter un portail pour les Pitons-du-Tonnerre ?'),
(348, 'deDE', 'Portal nach Donnerfels hinzufügen?'),
(348, 'zhCN', '添加通往雷霆崖的传送门？'),
(348, 'zhTW', '新增通往雷霆崖的傳送門？'),
(348, 'esES', '¿Añadir un portal a Cima del Trueno?'),
(348, 'esMX', '¿Añadir un portal a Cima del Trueno?'),
(348, 'ruRU', 'Добавить портал в Громовой Утес?'),

(349, 'enUS', 'Add Silvermoon Portal?'),
(349, 'koKR', '실버문 차원문을 추가하시겠습니까?'),
(349, 'frFR', 'Ajouter un portail pour Lune-d’argent ?'),
(349, 'deDE', 'Portal nach Silbermond hinzufügen?'),
(349, 'zhCN', '添加通往银月城的传送门？'),
(349, 'zhTW', '新增通往銀月城的傳送門？'),
(349, 'esES', '¿Añadir un portal a Lunargenta?'),
(349, 'esMX', '¿Añadir un portal a Lunargenta?'),
(349, 'ruRU', 'Добавить портал в Луносвет?'),

(350, 'enUS', 'Add Shattrath Portal?'),
(350, 'koKR', '샤트라스 차원문을 추가하시겠습니까?'),
(350, 'frFR', 'Ajouter un portail pour Shattrath ?'),
(350, 'deDE', 'Portal nach Shattrath hinzufügen?'),
(350, 'zhCN', '添加通往沙塔斯的传送门？'),
(350, 'zhTW', '新增通往撒塔斯的傳送門？'),
(350, 'esES', '¿Añadir un portal a Shattrath?'),
(350, 'esMX', '¿Añadir un portal a Shattrath?'),
(350, 'ruRU', 'Добавить портал в Шаттрат?'),

(351, 'enUS', 'Add Dalaran Portal?'),
(351, 'koKR', '달라란 차원문을 추가하시겠습니까?'),
(351, 'frFR', 'Ajouter un portail pour Dalaran ?'),
(351, 'deDE', 'Portal nach Dalaran hinzufügen?'),
(351, 'zhCN', '添加通往达拉然的传送门？'),
(351, 'zhTW', '新增通往達拉然的傳送門？'),
(351, 'esES', '¿Añadir un portal a Dalaran?'),
(351, 'esMX', '¿Añadir un portal a Dalaran?'),
(351, 'ruRU', 'Добавить портал в Даларан?'),

-- 360–370 : primary profession trainers labels
(360, 'enUS', 'Alchemy Trainer'),
(360, 'koKR', '연금술 전문 기술자'),
(360, 'frFR', 'Maître des alchimistes'),
(360, 'deDE', 'Alchemielehrer'),
(360, 'zhCN', '炼金术训练师'),
(360, 'zhTW', '鍊金術訓練師'),
(360, 'esES', 'Instructor de alquimia'),
(360, 'esMX', 'Instructor de alquimia'),
(360, 'ruRU', 'Учитель алхимии'),

(361, 'enUS', 'Blacksmithing Trainer'),
(361, 'koKR', '대장기술 전문 기술자'),
(361, 'frFR', 'Maître des forgerons'),
(361, 'deDE', 'Schmiedekunstlehrer'),
(361, 'zhCN', '锻造训练师'),
(361, 'zhTW', '鍛造訓練師'),
(361, 'esES', 'Instructor de herrería'),
(361, 'esMX', 'Instructor de herrería'),
(361, 'ruRU', 'Учитель кузнечного дела'),

(362, 'enUS', 'Engineering Trainer'),
(362, 'koKR', '기계공학 전문 기술자'),
(362, 'frFR', 'Maître des ingénieurs'),
(362, 'deDE', 'Ingenieurslehrer'),
(362, 'zhCN', '工程学训练师'),
(362, 'zhTW', '工程學訓練師'),
(362, 'esES', 'Instructor de ingeniería'),
(362, 'esMX', 'Instructor de ingeniería'),
(362, 'ruRU', 'Учитель инженерного дела'),

(363, 'enUS', 'Tailoring Trainer'),
(363, 'koKR', '재봉술 전문 기술자'),
(363, 'frFR', 'Maître des tailleurs'),
(363, 'deDE', 'Schneidereilehrer'),
(363, 'zhCN', '裁缝训练师'),
(363, 'zhTW', '裁縫訓練師'),
(363, 'esES', 'Instructor de sastrería'),
(363, 'esMX', 'Instructor de sastrería'),
(363, 'ruRU', 'Учитель портняжного дела'),

(364, 'enUS', 'Leatherworking Trainer'),
(364, 'koKR', '가죽세공 전문 기술자'),
(364, 'frFR', 'Maître des travailleurs du cuir'),
(364, 'deDE', 'Lederverarbeitungslehrer'),
(364, 'zhCN', '制皮训练师'),
(364, 'zhTW', '製皮訓練師'),
(364, 'esES', 'Instructor de peletería'),
(364, 'esMX', 'Instructor de peletería'),
(364, 'ruRU', 'Учитель кожевничества'),

(365, 'enUS', 'Skinning Trainer'),
(365, 'koKR', '무두질 전문 기술자'),
(365, 'frFR', 'Maître des dépeceurs'),
(365, 'deDE', 'Kürschnereilehrer'),
(365, 'zhCN', '剥皮训练师'),
(365, 'zhTW', '剝皮訓練師'),
(365, 'esES', 'Instructor de desuello'),
(365, 'esMX', 'Instructor de desuello'),
(365, 'ruRU', 'Учитель снятия шкур'),

(366, 'enUS', 'Mining Trainer'),
(366, 'koKR', '채광 전문 기술자'),
(366, 'frFR', 'Maître des mineurs'),
(366, 'deDE', 'Minenkundelehrer'),
(366, 'zhCN', '采矿训练师'),
(366, 'zhTW', '採礦訓練師'),
(366, 'esES', 'Instructor de minería'),
(366, 'esMX', 'Instructor de minería'),
(366, 'ruRU', 'Учитель горного дела'),

(367, 'enUS', 'Herbalism Trainer'),
(367, 'koKR', '약초채집 전문 기술자'),
(367, 'frFR', 'Maître des herboristes'),
(367, 'deDE', 'Kräuterkundelehrer'),
(367, 'zhCN', '草药学训练师'),
(367, 'zhTW', '草藥學訓練師'),
(367, 'esES', 'Instructor de herboristería'),
(367, 'esMX', 'Instructor de herboristería'),
(367, 'ruRU', 'Учитель травничества'),

(368, 'enUS', 'Enchanting Trainer'),
(368, 'koKR', '마법부여 전문 기술자'),
(368, 'frFR', 'Maître des enchanteurs'),
(368, 'deDE', 'Verzauberungslehrer'),
(368, 'zhCN', '附魔训练师'),
(368, 'zhTW', '附魔訓練師'),
(368, 'esES', 'Instructor de encantamiento'),
(368, 'esMX', 'Instructor de encantamiento'),
(368, 'ruRU', 'Учитель наложения чар'),

(369, 'enUS', 'Jewelcrafting Trainer'),
(369, 'koKR', '보석세공 전문 기술자'),
(369, 'frFR', 'Maître des joailliers'),
(369, 'deDE', 'Juwelierskunstlehrer'),
(369, 'zhCN', '珠宝加工训练师'),
(369, 'zhTW', '珠寶設計訓練師'),
(369, 'esES', 'Instructor de joyería'),
(369, 'esMX', 'Instructor de joyería'),
(369, 'ruRU', 'Учитель ювелирного дела'),

(370, 'enUS', 'Inscription Trainer'),
(370, 'koKR', '주문각인 전문 기술자'),
(370, 'frFR', 'Maître des calligraphes'),
(370, 'deDE', 'Inschriftenkundelehrer'),
(370, 'zhCN', '铭文训练师'),
(370, 'zhTW', '銘文學訓練師'),
(370, 'esES', 'Instructor de inscripción'),
(370, 'esMX', 'Instructor de inscripción'),
(370, 'ruRU', 'Учитель начертания'),

-- 380–390 : primary profession trainers confirmations
(380, 'enUS', 'Spawn Alchemy Trainer?'),
(380, 'koKR', '연금술 전문 기술자를 소환하시겠습니까?'),
(380, 'frFR', 'Invoquer un maître des alchimistes ?'),
(380, 'deDE', 'Alchemielehrer beschwören?'),
(380, 'zhCN', '生成炼金术训练师？'),
(380, 'zhTW', '召喚鍊金術訓練師？'),
(380, 'esES', '¿Invocar instructor de alquimia?'),
(380, 'esMX', '¿Invocar instructor de alquimia?'),
(380, 'ruRU', 'Призвать учителя алхимии?'),

(381, 'enUS', 'Spawn Blacksmithing Trainer?'),
(381, 'koKR', '대장기술 전문 기술자를 소환하시겠습니까?'),
(381, 'frFR', 'Invoquer un maître des forgerons ?'),
(381, 'deDE', 'Schmiedekunstlehrer beschwören?'),
(381, 'zhCN', '生成锻造训练师？'),
(381, 'zhTW', '召喚鍛造訓練師？'),
(381, 'esES', '¿Invocar instructor de herrería?'),
(381, 'esMX', '¿Invocar instructor de herrería?'),
(381, 'ruRU', 'Призвать учителя кузнечного дела?'),

(382, 'enUS', 'Spawn Engineering Trainer?'),
(382, 'koKR', '기계공학 전문 기술자를 소환하시겠습니까?'),
(382, 'frFR', 'Invoquer un maître des ingénieurs ?'),
(382, 'deDE', 'Ingenieurslehrer beschwören?'),
(382, 'zhCN', '生成工程学训练师？'),
(382, 'zhTW', '召喚工程學訓練師？'),
(382, 'esES', '¿Invocar instructor de ingeniería?'),
(382, 'esMX', '¿Invocar instructor de ingeniería?'),
(382, 'ruRU', 'Призвать учителя инженерного дела?'),

(383, 'enUS', 'Spawn Tailoring Trainer?'),
(383, 'koKR', '재봉술 전문 기술자를 소환하시겠습니까?'),
(383, 'frFR', 'Invoquer un maître des tailleurs ?'),
(383, 'deDE', 'Schneidereilehrer beschwören?'),
(383, 'zhCN', '生成裁缝训练师？'),
(383, 'zhTW', '召喚裁縫訓練師？'),
(383, 'esES', '¿Invocar instructor de sastrería?'),
(383, 'esMX', '¿Invocar instructor de sastrería?'),
(383, 'ruRU', 'Призвать учителя портняжного дела?'),

(384, 'enUS', 'Spawn Leatherworking Trainer?'),
(384, 'koKR', '가죽세공 전문 기술자를 소환하시겠습니까?'),
(384, 'frFR', 'Invoquer un maître des travailleurs du cuir ?'),
(384, 'deDE', 'Lederverarbeitungslehrer beschwören?'),
(384, 'zhCN', '生成制皮训练师？'),
(384, 'zhTW', '召喚製皮訓練師？'),
(384, 'esES', '¿Invocar instructor de peletería?'),
(384, 'esMX', '¿Invocar instructor de peletería?'),
(384, 'ruRU', 'Призвать учителя кожевничества?'),

(385, 'enUS', 'Spawn Skinning Trainer?'),
(385, 'koKR', '무두질 전문 기술자를 소환하시겠습니까?'),
(385, 'frFR', 'Invoquer un maître des dépeceurs ?'),
(385, 'deDE', 'Kürschnereilehrer beschwören?'),
(385, 'zhCN', '生成剥皮训练师？'),
(385, 'zhTW', '召喚剝皮訓練師？'),
(385, 'esES', '¿Invocar instructor de desuello?'),
(385, 'esMX', '¿Invocar instructor de desuello?'),
(385, 'ruRU', 'Призвать учителя снятия шкур?'),

(386, 'enUS', 'Spawn Mining Trainer?'),
(386, 'koKR', '채광 전문 기술자를 소환하시겠습니까?'),
(386, 'frFR', 'Invoquer un maître des mineurs ?'),
(386, 'deDE', 'Minenkundelehrer beschwören?'),
(386, 'zhCN', '生成采矿训练师？'),
(386, 'zhTW', '召喚採礦訓練師？'),
(386, 'esES', '¿Invocar instructor de minería?'),
(386, 'esMX', '¿Invocar instructor de minería?'),
(386, 'ruRU', 'Призвать учителя горного дела?'),

(387, 'enUS', 'Spawn Herbalism Trainer?'),
(387, 'koKR', '약초채집 전문 기술자를 소환하시겠습니까?'),
(387, 'frFR', 'Invoquer un maître des herboristes ?'),
(387, 'deDE', 'Kräuterkundelehrer beschwören?'),
(387, 'zhCN', '生成草药学训练师？'),
(387, 'zhTW', '召喚草藥學訓練師？'),
(387, 'esES', '¿Invocar instructor de herboristería?'),
(387, 'esMX', '¿Invocar instructor de herboristería?'),
(387, 'ruRU', 'Призвать учителя травничества?'),

(388, 'enUS', 'Spawn Enchanting Trainer?'),
(388, 'koKR', '마법부여 전문 기술자를 소환하시겠습니까?'),
(388, 'frFR', 'Invoquer un maître des enchanteurs ?'),
(388, 'deDE', 'Verzauberungslehrer beschwören?'),
(388, 'zhCN', '生成附魔训练师？'),
(388, 'zhTW', '召喚附魔訓練師？'),
(388, 'esES', '¿Invocar instructor de encantamiento?'),
(388, 'esMX', '¿Invocar instructor de encantamiento?'),
(388, 'ruRU', 'Призвать учителя наложения чар?'),

(389, 'enUS', 'Spawn Jewelcrafting Trainer?'),
(389, 'koKR', '보석세공 전문 기술자를 소환하시겠습니까?'),
(389, 'frFR', 'Invoquer un maître des joailliers ?'),
(389, 'deDE', 'Juwelierskunstlehrer beschwören?'),
(389, 'zhCN', '生成珠宝加工训练师？'),
(389, 'zhTW', '召喚珠寶設計訓練師？'),
(389, 'esES', '¿Invocar instructor de joyería?'),
(389, 'esMX', '¿Invocar instructor de joyería?'),
(389, 'ruRU', 'Призвать учителя ювелирного дела?'),

(390, 'enUS', 'Spawn Inscription Trainer?'),
(390, 'koKR', '주문각인 전문 기술자를 소환하시겠습니까?'),
(390, 'frFR', 'Invoquer un maître des calligraphes ?'),
(390, 'deDE', 'Inschriftenkundelehrer beschwören?'),
(390, 'zhCN', '生成铭文训练师？'),
(390, 'zhTW', '召喚銘文學訓練師？'),
(390, 'esES', '¿Invocar instructor de inscripción?'),
(390, 'esMX', '¿Invocar instructor de inscripción?'),
(390, 'ruRU', 'Призвать учителя начертания?'),

-- 400–402 : secondary profession trainers labels
(400, 'enUS', 'First Aid Trainer'),
(400, 'koKR', '응급치료 전문 기술자'),
(400, 'frFR', 'Maître des secouristes'),
(400, 'deDE', 'Lehrer für Erste Hilfe'),
(400, 'zhCN', '急救训练师'),
(400, 'zhTW', '急救訓練師'),
(400, 'esES', 'Instructor de primeros auxilios'),
(400, 'esMX', 'Instructor de primeros auxilios'),
(400, 'ruRU', 'Учитель первой помощи'),

(401, 'enUS', 'Fishing Trainer'),
(401, 'koKR', '낚시 전문 기술자'),
(401, 'frFR', 'Maître des pêcheurs'),
(401, 'deDE', 'Angellehrer'),
(401, 'zhCN', '钓鱼训练师'),
(401, 'zhTW', '釣魚訓練師'),
(401, 'esES', 'Instructor de pesca'),
(401, 'esMX', 'Instructor de pesca'),
(401, 'ruRU', 'Учитель рыбной ловли'),

(402, 'enUS', 'Cooking Trainer'),
(402, 'koKR', '요리 전문 기술자'),
(402, 'frFR', 'Maître des cuisiniers'),
(402, 'deDE', 'Kochkunstlehrer'),
(402, 'zhCN', '烹饪训练师'),
(402, 'zhTW', '烹飪訓練師'),
(402, 'esES', 'Instructor de cocina'),
(402, 'esMX', 'Instructor de cocina'),
(402, 'ruRU', 'Учитель кулинарии'),

-- 410–412 : secondary profession trainers confirmations
(410, 'enUS', 'Spawn First Aid Trainer?'),
(410, 'koKR', '응급치료 전문 기술자를 소환하시겠습니까?'),
(410, 'frFR', 'Invoquer un maître des secouristes ?'),
(410, 'deDE', 'Lehrer für Erste Hilfe beschwören?'),
(410, 'zhCN', '生成急救训练师？'),
(410, 'zhTW', '召喚急救訓練師？'),
(410, 'esES', '¿Invocar instructor de primeros auxilios?'),
(410, 'esMX', '¿Invocar instructor de primeros auxilios?'),
(410, 'ruRU', 'Призвать учителя первой помощи?'),

(411, 'enUS', 'Spawn Fishing Trainer?'),
(411, 'koKR', '낚시 전문 기술자를 소환하시겠습니까?'),
(411, 'frFR', 'Invoquer un maître des pêcheurs ?'),
(411, 'deDE', 'Angellehrer beschwören?'),
(411, 'zhCN', '生成钓鱼训练师？'),
(411, 'zhTW', '召喚釣魚訓練師？'),
(411, 'esES', '¿Invocar instructor de pesca?'),
(411, 'esMX', '¿Invocar instructor de pesca?'),
(411, 'ruRU', 'Призвать учителя рыбной ловли?'),

(412, 'enUS', 'Spawn Cooking Trainer?'),
(412, 'koKR', '요리 전문 기술자를 소환하시겠습니까?'),
(412, 'frFR', 'Invoquer un maître des cuisiniers ?'),
(412, 'deDE', 'Kochkunstlehrer beschwören?'),
(412, 'zhCN', '生成烹饪训练师？'),
(412, 'zhTW', '召喚烹飪訓練師？'),
(412, 'esES', '¿Invocar instructor de cocina?'),
(412, 'esMX', '¿Invocar instructor de cocina?'),
(412, 'ruRU', 'Призвать учителя кулинарии?'),

-- 413 : label "GM Island"
(413, 'enUS', 'GM Island'),
(413, 'koKR', 'GM 섬'),
(413, 'frFR', 'GM Island'),
(413, 'deDE', 'GM-Insel'),
(413, 'zhCN', 'GM岛'),
(413, 'zhTW', 'GM 島'),
(413, 'esES', 'GM Island'),
(413, 'esMX', 'GM Island'),
(413, 'ruRU', 'Остров GM'),

-- 414 : confirmation "Buy Guild House on GM Island?"
(414, 'enUS', 'Buy Guild House on GM Island?'),
(414, 'koKR', 'GM 섬에 길드 하우스를 구매하시겠습니까?'),
(414, 'frFR', 'Acheter une maison de guilde sur GM Island ?'),
(414, 'deDE', 'Gildenhaus auf GM Island kaufen?'),
(414, 'zhCN', '在GM岛购买公会大厅？'),
(414, 'zhTW', '在 GM 島購買公會會館？'),
(414, 'esES', '¿Comprar una casa de hermandad en GM Island?'),
(414, 'esMX', '¿Comprar una casa de hermandad en GM Island?'),
(414, 'ruRU', 'Купить дом гильдии на острове GM?');


-- ============================================================================
-- 7. 설치 결과 확인
-- ============================================================================
USE `acore_characters`;
SELECT 'characters.guild_house' AS `check_item`, COUNT(*) AS `row_count`
  FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'guild_house';

USE `acore_world`;

SELECT `entry`, `name`, `subname`, `ScriptName`
  FROM `creature_template`
 WHERE `entry` BETWEEN 500030 AND 500032
 ORDER BY `entry`;

SELECT `CreatureID`, `CreatureDisplayID`, `DisplayScale`, `Probability`
  FROM `creature_template_model`
 WHERE `CreatureID` BETWEEN 500030 AND 500032
 ORDER BY `CreatureID`, `Idx`;

SELECT COUNT(*) AS `guild_house_spawns_count`
  FROM `guild_house_spawns`;

SELECT COUNT(*) AS `koKR_locale_count`
  FROM `mod_guildhouse_locale`
 WHERE `Locale` = 'koKR';

SELECT
    @GH_CREATURE_ENTRY_COL AS `detected_creature_entry_column`,
    @GH_GAMEOBJECT_ENTRY_COL AS `detected_gameobject_entry_column`;

SET SESSION FOREIGN_KEY_CHECKS = @GH_OLD_FOREIGN_KEY_CHECKS;
SET SESSION SQL_MODE = @GH_OLD_SQL_MODE;