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