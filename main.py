import pandas as pd
import streamlit as st

exchange_rate = 1350

df_test = pd.read_csv('./data/test.csv')

df_test['1주당_손실액'] = df_test['1주당_매도가격'] - df_test['1주당_취득가액']
df_test['1주당_손실액_환율'] = df_test['1주당_손실액'] * exchange_rate
df_test['손실율'] = round((df_test['1주당_매도가격'] - df_test['1주당_취득가액'])*100/df_test['1주당_매도가격'], 2)

def find_loss_stock(df):
    df_loss = df[df['손실율'] == df['손실율'].min()]
    df_loss = df_loss if df_loss.shape[0] == 1 else df_loss[df_loss['1주당_매도가격'] == df_loss['1주당_매도가격'].min()]

    return df_loss

def tax_loss_harvesting(df, money, dict, accounting_number):
    df1 = df[df['계좌번호'] == accounting_number]
    df_loss = find_loss_stock(df1)

    df_loss_money = df_loss['1주당_손실액_환율'].values[0]
    df_loss_quantity = df_loss['보유수량'].values[0]

    loss_money = df_loss_money * df_loss_quantity

    result_money = loss_money + money

    if result_money >= 0:
        print(f"{df_loss['종목코드'].values[0]}를 {df_loss_quantity}주 만큼 파세요 ")
        print(f"손실 금액 : {df_loss['1주당_손실액_환율'].values[0] * df_loss['보유수량'].values[0]}")
        df_remain = df.drop(df_loss.index).reset_index(drop=True)

        dict['종목코드'].append(df_loss['종목코드'].values[0])
        dict['매도주수'].append(df_loss_quantity)
        dict['매도금액'].append(df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity)
        # 2번쨰 손실이 큰 종목 선정
        tax_loss_harvesting(df_remain, result_money, dict, accounting_number)
    else:
        df_loss_quantity = df_loss_quantity - 1
        while (df_loss_money * df_loss_quantity) + money < 0:
            df_loss_quantity = df_loss_quantity - 1
            if (df_loss_money * df_loss_quantity) + money >= 0:
                print(f"{df_loss['종목코드'].values[0]}를 {df_loss_quantity}주 만큼 파세요 ")
                print(f"손실 금액 : {df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity}")

                dict['종목코드'].append(df_loss['종목코드'].values[0])
                dict['매도주수'].append(df_loss_quantity)
                dict['매도금액'].append(df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity)
                break
            elif len(dict['종목코드']) == 3:
                break

    return pd.DataFrame(dict)

if __name__ == "__main__" :
    df = df_test
    money = 1500000
    dic = {'종목코드' : [], '매도주수' : [], '매도금액' : []}
    accounting_number = '계좌1'

    st.set_page_config(layout = 'wide')
    st.title("매도주수 추천기")
    accounting_select_box = st.selectbox("계좌번호", (['계좌1', '계좌2', '계좌3', '계좌4', '계좌5']))
    st.write(f"과세표준 : {format(money, ',')}원")
    st.write(f"절세 전 해외주식 양도세 : {format(round(money * 0.22), ',')}원")
    TLH_result = tax_loss_harvesting(df_test, money, dict=dic, accounting_number=accounting_select_box)
    st.write(f"손실 금액 더한 후 과세표준: {format(money + TLH_result['매도금액'].sum(), ',')}원")
    st.write(f"절세 후 해외주식 양도세 : {format(round((money + TLH_result['매도금액'].sum()) * 0.22), ',')}원")

    col1, col2 = st.columns(2)

    with col1 :
        st.write("손실 종목 리스트")
        st.write(df[df['계좌번호']==accounting_select_box].reset_index(drop=True))
    with col2 :
        st.write('매도 추천 종목 리스트')
        st.write(TLH_result)