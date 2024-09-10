import pandas as pd
import numpy as np
import streamlit as st
import os.path
import requests
import json
import xlrd

#실제 dev 계좌 테스트
# df = pd.read_csv("./data/dev_20240906.csv") # 데이터 로드

df = pd.read_excel("./data/dev_20240909.xlsx", engine="openpyxl", usecols="A:O")
df['1주당_취득가액'] = df['매입단가(원화)']
df['1주당_매도가격'] = np.floor(df['전일종가']*df['기준환율'])
df['1주당_손실액'] = df['1주당_매도가격'] - df['1주당_취득가액']

df['평가금액(원화)'] = np.floor(df['평가금액']*df['기준환율'])
df['손실율'] = round((df['1주당_매도가격'] - df['1주당_취득가액'])*100 / df['1주당_취득가액'], 2)

df['손실금액'] = np.floor((df['평가금액(원화)'] - df['매입금액(원화)'])*(df['총보유수량']/df['보유수량']))
df['매도금액'] = np.floor(df['평가금액(원화)']*(df['총보유수량']/df['보유수량']))

### API호출
def call_api(cano_number, prdt_number, money, customer_name) :
    url = f"https://dev-feature.kis.finance/overseas-tax-saving/mock/asset/v1/overseas-stock/test/trp8101r?cano={cano_number}&acntPrdtCd={prdt_number}&txbsAmt={money}"
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        data = response.json()
        json_data = json.dumps(data, indent=4)
        df = pd.read_json(json_data)
        df['ACCOUNTING'] = df["CANO"].map(str) +"-"+df["ACNT_PRDT_CD"].map(str)
        df['CUSTOMER'] = customer_name
        df1 = df[['CUSTOMER', 'ACCOUNTING', "PDNO", "PRDT_NAME","FRST_BLTN_EXRT", "FRCR_AQST_UNPR", "HLDG_QTY", "RCMD_SLL_FRCR_UNPR", "RCMD_SLL_QTY"]]
        df1.columns = ["고객명", "게좌번호", "종목코드", "종목명", "고시환율","매입단가","보유수량","매도추천단가", "매도추천수량"]
        df1 = df1[df1["매도추천수량"]!=0]
        return df1
    else:
        print("Request failed with status code:", response.status_code)

def find_loss_stock_buffer(df):
    # 총 보유수량이 0인 종목은 제외하여 추천
    # 종목 당 손실금액 : 손실금액의 절대값이 클 수록 (buffer1)
    # 종목 당 손실률 : 손실률의 절대값이 클수록 (buffer2)
    # 종목 당 매도금액 : 매도금액이 작을수록 (buffer3)
    # 종목의 1주 당 가격 : 매도금액이 작을수록 (buffer4)
    # df1 = df[df['총보유수량']!=0]
    df = df[df['손실금액']<0]

    buffer1 = df['손실금액'].min() * (-0.05) # 손실금액 버퍼 구하기
    df_loss = df[(df['손실금액'] >= (df['손실금액'].min() - buffer1)) & (df['손실금액'] <= (df['손실금액'].min() + buffer1))]
    if df_loss.shape[0] == 1:
        return df_loss
    else:
        buffer2 = df['손실율'].min() * (-0.05) # 손실율 버퍼 구하기
        df_loss = df[(df['손실율'] >= (df['손실율'].min() - buffer2)) & (df['손실율'] <= (df['손실율'].min() + buffer2))]
        if df_loss.shape[0] == 1:
            return df_loss
        else:
            buffer3 = df['매도금액'].min() * (0.05) # 매도금액 버퍼 구하기
            df_loss = df[(df['매도금액'] >= (df['매도금액'].min() - buffer3)) & (df['매도금액'] <= (df['매도금액'].min() + buffer3))]
            if df_loss.shape[0] == 1:
                return df_loss
            else:
                buffer4 = df['1주당_매도가격'].min() * (0.05) # 매도가격 버퍼 구하기
                df_loss = df[(df['1주당_매도가격'] >= (df['1주당_매도가격'].min() - buffer4)) & (df['1주당_매도가격'] <= (df['1주당_매도가격'].min() + buffer4))]
                if df_loss.shape[0] == 1:
                    return df_loss
                else:
                    return pd.DataFrame()
                    print("!!!추천불가!!!")

def tax_loss_harvesting(df, money, saved_df, saving_dic, customer_number, accounting_number, buffer):
    """
    :param df: 전체 고객과 계좌의 손실 종목 보유 잔고
    :param money: 절세시켜야하는 금액(=과세표준)
    :param saved_df: 이미 예약 주문 나간 내역
    :param saving_dic: 알고리즘의 결과로 저장될 내역
    :param customer_number: 고객번호
    :param accounting_number: 계좌번호
    :param buffer: 과세표준의 안전장치 버퍼
    :return: DataFrame
    """
    df1 = df[(df['고객번호'] == customer_number) & (df['계좌번호'] == accounting_number)] # 고객번호&계좌번호로 필터링
    df_loss = find_loss_stock_buffer(df1)  # 알고리즘 기준을 만족하는 종목 선정

    if df_loss.shape[0] != 0 :

        # loss_money = df_loss['1주당_손실액'].values[0] * df_loss['총보유수량'].values[0] # 매도 기준에 선정된 종목의 1주당 손실액 * 총보유수량(기체결 수량 제외)
        loss_money = df_loss['손실금액'].values[0]
        saved_df_money = saved_df[saved_df['고객번호'] == customer_number]['손실금액'].sum()
        result_money = money * (1-buffer) + loss_money + saved_df_money
        # print("----------")
        # print(result_money)
        # print("----------")
        print(df_loss)

        if result_money >= 0: # 결과가 양수라면 총 보유수량 그대로 넣으면 됨
            if len(saving_dic['종목코드']) == 5 : # 5종목으로 채워졌을 경우 추천 종료
                return pd.DataFrame(saving_dic)

            print(f"{df_loss['종목코드'].values[0]}를 {df_loss['총보유수량'].values[0]}주 만큼 파세요")
            print(f"손실 금액 : {loss_money}")
            print(f"남은 과세표준 : {result_money}")
            print("===========================")
            df_remain = df.drop(df_loss.index).reset_index(drop=True) # 추천 종료된 종목은 제외

            saving_dic['고객번호'].append(customer_number)
            saving_dic['계좌번호'].append(accounting_number)
            saving_dic['종목코드'].append(df_loss['종목코드'].values[0])
            saving_dic['매도수량'].append(df_loss['총보유수량'].values[0])
            saving_dic['손실금액'].append(loss_money)

            # 2번째 기준에 부합하는 종목 선정
            tax_loss_harvesting(df_remain, money*(1-buffer) + loss_money, saved_df, saving_dic, customer_number, accounting_number, buffer=0)

        else: # 결과가 음수라면 총보유수량을 하나씩 줄여가며 금액 확인 계산
            df_loss_quantity = df_loss['총보유수량'].values[0]
            while money * (1-buffer) + (df_loss['1주당_손실액'].values[0] * df_loss_quantity)  + saved_df_money < 0:
                df_loss_quantity = df_loss_quantity - 1
                if money * (1-buffer) + (df_loss['1주당_손실액'].values[0] * df_loss_quantity) + saved_df_money >= 0:
                    if df_loss_quantity == 0 : # 주수가 0주라면 넣을 종목이 없는 것이므로 다음 기준에 해당하는 종목 선정 뒤 break
                        df_remain = df.drop(df_loss.index).reset_index(drop=True)
                        tax_loss_harvesting(df_remain, money, saved_df, saving_dic, customer_number, accounting_number, buffer)
                        break

                    print(f"{df_loss['종목코드'].values[0]}를 {df_loss_quantity}주 만큼 파세요")
                    print(f"손실 금액 : {df_loss['1주당_손실액'].values[0] * df_loss_quantity}")
                    print(f"남은 과세표준 : {money * (1-buffer) + df_loss['1주당_손실액'].values[0] * df_loss_quantity + saved_df_money}")
                    print("-------------------------------")

                    saving_dic['고객번호'].append(customer_number)
                    saving_dic['계좌번호'].append(accounting_number)
                    saving_dic['종목코드'].append(df_loss['종목코드'].values[0])
                    saving_dic['매도수량'].append(df_loss_quantity)
                    saving_dic['손실금액'].append(df_loss['1주당_손실액'].values[0] * df_loss_quantity)
                    print(saving_dic)

                    if df_loss_quantity < df_loss['총보유수량'].values[0]: # 더 손실 시켜야하는 금액이 남은 상태에서 다음 종목으로 그 손실을 시킬 수 있는 경우
                        df_remain = df.drop(df_loss.index).reset_index(drop=True)
                        tax_loss_harvesting(df_remain, df_loss['1주당_손실액'].values[0] * df_loss_quantity + money * (1-buffer), saved_df, saving_dic, customer_number, accounting_number, buffer=0)
                        break
                    break
                elif len(saving_dic['종목코드']) == 5: # 종목수 5종목으로 제한
                    break
                elif df_loss_quantity <= 0 : # 음수 방지
                    break
        return pd.DataFrame(saving_dic)
    else :
        return pd.DataFrame({'고객번호' : [], '계좌번호' : [], '종목코드' : [], '매도수량' : [], '손실금액' : []})
        print("!!!손실 종목이 없습니다!!!")

if __name__ == "__main__" :
    saving_dic = {'고객번호' : [], '계좌번호' : [], '종목코드' : [], '매도수량' : [], '손실금액' : []}
    if os.path.isfile("./data/saved_df_20240905.csv"):
        saved_df = pd.read_csv("./data/saved_df_20240905.csv")
    else:
        saved_df = pd.DataFrame(columns = ['고객번호', '계좌번호', '종목코드', '매도수량', '손실금액'])
    st.set_page_config(layout = 'wide')
    st.title("해외주식 양도세 줄이기 : 매도 추천 종목 & 수량 솔루션")

    customer_select_box = st.selectbox("고객번호", (list(df['고객번호'].unique())))
    accounting_select_box = st.selectbox("계좌번호", (list(df['계좌번호'].unique())))
    money = st.text_input("손실 시켜야하는 금액(과세표준)을 입력하세요.", value = 1000000)
    TLH_result = tax_loss_harvesting(df, int(money), saved_df=saved_df, saving_dic=saving_dic,
                                     customer_number=customer_select_box, accounting_number=accounting_select_box,
                                     buffer=0.1)

    col1, col2, col3 = st.columns(3)
    with col1:
        container1 = st.container(border=True)
        container1.write(f"과세표준 : {format(int(money), ',')}원")
        container1.write(f":green[버퍼(%) : 90%]")
        container1.write(f"버퍼(%) 적용 후 과세표준 : {format(int(float(money) * (1 - 0.1)), ',')}원")

    with col2:
        container2 = st.container(border=True)
        container2.write("<매도 시 발생 손실 금액 예상>")
        container2.write(f"시뮬레이션 손실 금액 : {format(int(TLH_result['손실금액'].sum()), ',')}원")

    with col3:
        container3 = st.container(border=True)
        container3.write("<양도소득세>")
        container3.write(f":red[절세 전 해외주식 양도소득세 : {format(round(int(money) * 0.22), ',')}원]")
        money2 = round(int(money) * 0.22) if int(money) < round(int(-(TLH_result['손실금액'].sum()))) else round(int(-(TLH_result['손실금액'].sum()) * 0.22))
        container3.write(f"줄일 수 있는 양도소득세 : {format(money2, ',')}원")
        container3.write(f"절세 후 해외주식 양도소득세 : {format(round(int(money) * 0.22) - money2, ',')}원")

    col4, col5 = st.columns(2)

    with col4 :
        st.write('<매도 추천 종목 리스트-파이썬>')
        st.write(TLH_result)
    with col5 :
        st.write('<매도 추천 종목 리스트-TR>')
        st.write(call_api(accounting_select_box.split("-")[0], accounting_select_box.split("-")[1], int(money), customer_select_box))

    # with col4 :
    st.write("<손실 종목 리스트>")
    st.write(df[df['계좌번호'] == accounting_select_box].reset_index(drop=True))

    if st.button("예약매도전송") :
        print("전송완료")
        pd.concat([saved_df, TLH_result]).to_csv("./data/saved_df_20240905.csv", index=False)