# �ձ��齫

## ����

����Ŀ����һ����C++ʵ�ֵ��ձ��齫��Ϸ�������ṩ�ӿڣ��Ա㣺
	
	ʵ�ֲ�ͬ�����AI Agent
	��������

## �����ܹ�

Table�ࣺ���������࣬����������Ϸ���漰�������б����Ŀ���
Player�ࣺװ����Table�ڣ����ڴ��������Ϣ
Tile.h��ͨ��BaseTile������࣬ͨ��Tile���һ���Ƶ���Ϣ
Rule.h��ͨ����Table�л�õĺ�Tile��Player������ص���Ϣ�����Ժ��ƣ��ԣ������ܣ��������ƵȽ����ж�
GameLog.h���ṩһ��ͨ�õ���Ϸ��¼�������Լ�¼��ҿ��Կ�������Ϣ��������Ϸ��ȫ����¼��
TableStatus.h���ṩ��Agent�������ࡣͨ��GameLog��������Ҫ����Ϣ��
Agent�ࣺ���ڽ���ʵ����Ϸ����ĳ�����ࡣ��ͨ��TableStatus���Լ��ṩ�Ŀ���Action�������ṩһ��ѡ��

MahjongAlgorithm�ļ��У�һ���������ģ����Խ��ƽ���3n+2���Ŀ⡣

## �㷨

### Table::GameProcess

������������漰��һ������Ϸ���̿��ơ�

��һ������ʼ������
	��ɽ
	ÿ���˵ĳ�ʼ��13����
	��ʼ�����磬�ŷ�
	��ʼ��ÿ���˵���ֱ״̬
	��Agentע�����
	��ʼ��ׯ�ҵı��
	��ʼ��turn����=ׯ��

	��غ�=True

�ڶ�������ѭ��
	1. ����player[turn]��ͨ��GetValidAction�����vector<SelfAction> valid_action
	2. ͨ��Player[turn].gameLog������TableStatus����table_status
	3. ����agent[turn].get_self_action������valid_action, table_status�����decision(��������)
	4. ����valid_action[decision].action�����벻ͬ�ķ�֧�����������������5


### GetValidAction
