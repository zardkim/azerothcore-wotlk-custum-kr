-- ============================================================================
-- 통합: 04 (렙제 없애기) + 05 (속옷-999) — 원본 그대로 이어붙임, 둘 다 acore_world 대상
-- ============================================================================

# 수정할 디비를 선택합니다.
USE acore_world;

# 36칸가방 렙제한 없애기
UPDATE `item_template` SET 
	`RequiredLevel`=0, `RequiredSkill`=0, `RequiredSkillRank`=0
WHERE entry='23162';

# 날탈 랩제한 없애기
UPDATE `item_template` SET 
	`RequiredLevel`=0, `RequiredSkill`=0, `RequiredSkillRank`=0
WHERE entry='701000';

# 날쌘줄리안 호랑이 랩제한 없애기
UPDATE `item_template` SET 
	`RequiredLevel`=0, `RequiredSkill`=0, `RequiredSkillRank`=0
WHERE entry='19902';
-- ---- 05 속옷-999.sql ----
# 수정할 디비를 선택합니다.
USE acore_world;

# 기존에 생성된 아이템이 있다면 삭제, entry 1000000 은 리팩에 절대 존재하지 않는 아이템이므로 상관없습니다.
# DELETE FROM item_template WHERE entry = 1000000;	

# 실제 속옷 아이템을 추가하는 부분입니다.
# entry : 아이템 ID
# class, subclass : 아이템 종류 (속옷)
# name : 아이템 이름
# displayid : 아이템 이미지
# Quality : 아이템 등급
# StatsCount : 적용되는 스탯의 개수 *중요* (스탭을 힘, 민첩을 2개를 추가했으면 2이고 힘, 민첩, 생명 이렇게 3개를 추가하면 3이 됩니다.)
# stat_type1 ~ 10 : 추가할 스탯의 종류 (0:마나, 1:생명, 3:민첩, 4:힘, 5:지능, 6:정신, 7:체력, 31:적중도, 32:크리티컬, 38:전투력, 44: 관통력, 46:생명력 회복량)
# stat_value1 ~ 10 : 추가할 스탯의 값
# dmg_min1, dmg_max1 : 최소 최대 대미지
# dmg_type1 : 데미지타입 (0: 물리, 1: 신성, 2: 불, 3: 자연, 4:냉기, 5:암흠, 6:비전)
# armor : 방어도
# holy_res~arcane_res : 저항
# 요그 학살자의 셔츠 업데이트
UPDATE `item_template` SET 
	`class`=4, `subclass`=0, `SoundOverrideSubclass`=-1, `Quality`=4, 
	`Flags`=0, `FlagsExtra`=0, `BuyCount`=1, `BuyPrice`=0, `SellPrice`=1, `InventoryType`=4, `AllowableClass`=-1, `AllowableRace`=-1, 
	`ItemLevel`=226, `RequiredLevel`=0, `RequiredSkill`=0, `RequiredSkillRank`=0, `requiredspell`=0, `requiredhonorrank`=0, `RequiredCityRank`=0, 
	`RequiredReputationFaction`=0, `RequiredReputationRank`=0, `maxcount`=0, `stackable`=1, `ContainerSlots`=0, `stat_type1`=1, `stat_value1`=999, `stat_type2`=3, `stat_value2`=999, `stat_type3`=4, `stat_value3`=999, `stat_type4`=7, `stat_value4`=999, `stat_type5`=31, `stat_value5`=999,
	`stat_type6`=32, `stat_value6`=999, `stat_type7`=38, `stat_value7`=500, `stat_type8`=44, `stat_value8`=999, `stat_type9`=46, `stat_value9`=100, `stat_type10`=0, `stat_value10`=0,
	`ScalingStatDistribution`=0, `ScalingStatValue`=0, `dmg_min1`=0, `dmg_max1`=0, `dmg_type1`=0, `dmg_min2`=0, `dmg_max2`=0, `dmg_type2`=0,
	`armor`=999, `holy_res`=999, `fire_res`=999, `nature_res`=999, `frost_res`=999, `shadow_res`=999, `arcane_res`=999, `delay`=1000, `ammo_type`=0, `RangedModRange`=0,
	`spellid_1`=63388, `spelltrigger_1`=0, `spellcharges_1`=0, `spellppmRate_1`=0, `spellcooldown_1`=-1, `spellcategory_1`=0, `spellcategorycooldown_1`=-1,
	`spellid_2`=0, `spelltrigger_2`=0, `spellcharges_2`=0, `spellppmRate_2`=0, `spellcooldown_2`=-1, `spellcategory_2`=0, `spellcategorycooldown_2`=-1,
	`spellid_3`=0, `spelltrigger_3`=0, `spellcharges_3`=0, `spellppmRate_3`=0, `spellcooldown_3`=-1, `spellcategory_3`=0, `spellcategorycooldown_3`=-1,
	`spellid_4`=0, `spelltrigger_4`=0, `spellcharges_4`=0, `spellppmRate_4`=0, `spellcooldown_4`=-1, `spellcategory_4`=0, `spellcategorycooldown_4`=-1,
	`spellid_5`=0, `spelltrigger_5`=0, `spellcharges_5`=0, `spellppmRate_5`=0, `spellcooldown_5`=-1, `spellcategory_5`=0, `spellcategorycooldown_5`=-1,
	`bonding`=0, `PageText`=0, `LanguageID`=0, `PageMaterial`=0, `startquest`=0, `lockid`=0, `Material`=7, `sheath`=0, `RandomProperty`=0, `RandomSuffix`=0,
	`block`=0, `itemset`=0, `MaxDurability`=0, `area`=0, `Map`=0, `BagFamily`=0, `TotemCategory`=0, `socketColor_1`=0, `socketContent_1`=0, `socketColor_2`=0, `socketContent_2`=0,
	`socketColor_3`=0, `socketContent_3`=0, `socketBonus`=0, `GemProperties`=0, `RequiredDisenchantSkill`=375, `ArmorDamageModifier`=0, `duration`=0, `ItemLimitCategory`=0,
	`HolidayId`=0, `ScriptName`='', `DisenchantID`=54, `FoodType`=0, `minMoneyLoot`=0, `maxMoneyLoot`=0, `flagsCustom`=0, `VerifiedBuild`=1
WHERE entry='46104';

# 저렙용 shurts_of_uber 업데이트
UPDATE `item_template` SET 
	`class`=4, `subclass`=0, `SoundOverrideSubclass`=-1, `Quality`=4, 
	`Flags`=0, `FlagsExtra`=0, `BuyCount`=1, `BuyPrice`=0, `SellPrice`=1, `InventoryType`=4, `AllowableClass`=-1, `AllowableRace`=-1, 
	`ItemLevel`=226, `RequiredLevel`=0, `RequiredSkill`=0, `RequiredSkillRank`=0, `requiredspell`=0, `requiredhonorrank`=0, `RequiredCityRank`=0, 
	`RequiredReputationFaction`=0, `RequiredReputationRank`=0, `maxcount`=0, `stackable`=1, `ContainerSlots`=0, `stat_type1`=1, `stat_value1`=99, `stat_type2`=3, `stat_value2`=99, `stat_type3`=4, `stat_value3`=99, `stat_type4`=7, `stat_value4`=99, `stat_type5`=31, `stat_value5`=99,
	`stat_type6`=32, `stat_value6`=99, `stat_type7`=38, `stat_value7`=50, `stat_type8`=44, `stat_value8`=99, `stat_type9`=46, `stat_value9`=10, `stat_type10`=0, `stat_value10`=0,
	`ScalingStatDistribution`=0, `ScalingStatValue`=0, `dmg_min1`=0, `dmg_max1`=0, `dmg_type1`=0, `dmg_min2`=0, `dmg_max2`=0, `dmg_type2`=0,
	`armor`=99, `holy_res`=99, `fire_res`=99, `nature_res`=99, `frost_res`=99, `shadow_res`=99, `arcane_res`=99, `delay`=1000, `ammo_type`=0, `RangedModRange`=0,
	`spellid_1`=63388, `spelltrigger_1`=0, `spellcharges_1`=0, `spellppmRate_1`=0, `spellcooldown_1`=-1, `spellcategory_1`=0, `spellcategorycooldown_1`=-1,
	`spellid_2`=0, `spelltrigger_2`=0, `spellcharges_2`=0, `spellppmRate_2`=0, `spellcooldown_2`=-1, `spellcategory_2`=0, `spellcategorycooldown_2`=-1,
	`spellid_3`=0, `spelltrigger_3`=0, `spellcharges_3`=0, `spellppmRate_3`=0, `spellcooldown_3`=-1, `spellcategory_3`=0, `spellcategorycooldown_3`=-1,
	`spellid_4`=0, `spelltrigger_4`=0, `spellcharges_4`=0, `spellppmRate_4`=0, `spellcooldown_4`=-1, `spellcategory_4`=0, `spellcategorycooldown_4`=-1,
	`spellid_5`=0, `spelltrigger_5`=0, `spellcharges_5`=0, `spellppmRate_5`=0, `spellcooldown_5`=-1, `spellcategory_5`=0, `spellcategorycooldown_5`=-1,
	`bonding`=0, `PageText`=0, `LanguageID`=0, `PageMaterial`=0, `startquest`=0, `lockid`=0, `Material`=7, `sheath`=0, `RandomProperty`=0, `RandomSuffix`=0,
	`block`=0, `itemset`=0, `MaxDurability`=0, `area`=0, `Map`=0, `BagFamily`=0, `TotemCategory`=0, `socketColor_1`=0, `socketContent_1`=0, `socketColor_2`=0, `socketContent_2`=0,
	`socketColor_3`=0, `socketContent_3`=0, `socketBonus`=0, `GemProperties`=0, `RequiredDisenchantSkill`=375, `ArmorDamageModifier`=0, `duration`=0, `ItemLimitCategory`=0,
	`HolidayId`=0, `ScriptName`='', `DisenchantID`=54, `FoodType`=0, `minMoneyLoot`=0, `maxMoneyLoot`=0, `flagsCustom`=0, `VerifiedBuild`=1
WHERE entry='45280';