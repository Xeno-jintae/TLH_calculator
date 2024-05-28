import pandas as pd
import streamlit as st

exchange_rate = 1350


df = pd.read_excel("/Users/xeno/Desktop/work_code/절세서비스/TLH/data/real_account_test.xlsx") # 데이터 로드
df['1주당_취득가액'] = round(df['매입원가'] / df['보유수량'])
df['1주당_매도가격'] = round(df['평가금액'] / df['보유수량'])
df['1주당_손실액_환율'] = df['1주당_매도가격'] - df['1주당_취득가액']
df['손실율'] = round((df['1주당_매도가격'] - df['1주당_취득가액'])*100/df['1주당_취득가액'],2)
df['손실금액'] = df['1주당_손실액_환율'] * df['보유수량'] # 종목당 손실금액
df['매도금액'] = df['평가금액'] # 종목당 매도금액
df.rename(columns={'티커' : '종목코드'}, inplace=True)

df_test = pd.read_csv('./data/test2.csv') # 데이터 로드
df_test['1주당_손실액'] = df_test['1주당_매도가격'] - df_test['1주당_취득가액'] # 1주당 손실액 구하기
df_test['1주당_손실액_환율'] = df_test['1주당_손실액'] * 1350 # 환율(1,350원 고정) 적용
df_test['손실율'] = round((df_test['1주당_매도가격'] - df_test['1주당_취득가액'])*100/df_test['1주당_취득가액'],2) # 손실율
df_test['손실금액'] = df_test['1주당_손실액_환율'] * df_test['보유수량'] # 종목당 손실금액
df_test['매도금액'] = df_test['1주당_매도가격'] * df_test['보유수량'] * 1350 # 종목당 매도금액

def find_loss_stock_buffer(df):
    # 종목 당 손실금액 : 손실금액의 절대값이 클 수록 (buffer1)
    # 종목 당 손실률 : 손실률의 절대값이 클수록 (buffer2)
    # 종목 당 매도금액 : 매도금액이 작을수록 (buffer3)
    # 종목의 1주 당 가격 : 매도금액이 작을수록 (buffer4)

    buffer1 = df['손실금액'].min() * (-0.05) # 손실금액 버퍼 구하기
    df_loss = df[(df['손실금액'] >= df['손실금액'].min() - buffer1) & (df['손실금액'] <= df['손실금액'].min() + buffer1)]

    if df_loss.shape[0] == 1:
        return df_loss
    else:
        buffer2 = df_loss['손실율'].min() * (-0.05) # 손실율 버퍼 구하기
        df_loss = df_loss[
            (df_loss['손실율'] >= df_loss['손실율'].min() - buffer2) & (df_loss['손실율'] <= df_loss['손실율'].min() + buffer2)]
        if df_loss.shape[0] == 1:
            return df_loss
        else:
            buffer3 = df_loss['매도금액'].min() * (0.05) # 매도금액 버퍼 구하기
            df_loss = df_loss[(df_loss['매도금액'] >= df_loss['매도금액'].min() - buffer3) & (
                        df_loss['매도금액'] <= df_loss['매도금액'].min() + buffer3)]
            if df_loss.shape[0] == 1:
                return df_loss
            else:
                buffer4 = df_loss['1주당_매도가격'].min() * (0.05) # 매도가격 버퍼 구하기
                df_loss = df_loss[(df_loss['매도금액'] >= df_loss['매도금액'].min() - buffer3) & (
                            df_loss['1주당_매도가격'] <= df_loss['1주당_매도가격'].min() + buffer4)]
                if df_loss.shape[0] == 1:
                    return df_loss
                else:
                    return pd.DataFrame()
                    print("추천불가")

def tax_loss_harvesting(df, money, dict, accounting_number, buffer):
    df1 = df[df['계좌번호'] == accounting_number]
    df_loss = find_loss_stock_buffer(df1)  # 알고리즘 기준을 만족하는 종목 선정

    if df_loss.shape[0] != 0 :

        loss_money = df_loss['손실금액'].values[0] # 선정된 종목의 총 손실 금액

        result_money = loss_money + money + buffer # 손실 금액 + 손실 시켜야 하는 금액 + 환율 고려한 버퍼 금액

        if result_money >= 0: # 결과가 양수라면 매도하면 됨
            print(f"{df_loss['종목코드'].values[0]}를 {df_loss['보유수량'].values[0]}주 만큼 파세요")
            print(f"손실 금액 : {loss_money}")
            df_remain = df.drop(df_loss.index).reset_index(drop=True)

            dict['종목코드'].append(df_loss['종목코드'].values[0])
            dict['매도주수'].append(df_loss['보유수량'].values[0])
            dict['매도금액'].append(loss_money)
            print(result_money)
            # 2번째 기준에 부합하는 종목 선정
            tax_loss_harvesting(df_remain, result_money, dict, accounting_number, 0)
        else: # 결과가 음수라면 주수를 줄여가며 금액 확인
            df_loss_quantity = df_loss['보유수량'].values[0]
            while (df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity) + money + buffer < 0:
                df_loss_quantity = df_loss_quantity - 1
                if (df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity) + money + buffer >= 0:
                    if df_loss_quantity == 0 : # 주수가 0주라면 break
                        df_remain = df.drop(df_loss.index).reset_index(drop=True)
                        tax_loss_harvesting(df_remain, money, dict, accounting_number, buffer)
                        break
                    print(f"{df_loss['종목코드'].values[0]}를 {df_loss_quantity}주 만큼 파세요")
                    print(f"손실 금액 : {df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity}")

                    dict['종목코드'].append(df_loss['종목코드'].values[0])
                    dict['매도주수'].append(df_loss_quantity)
                    dict['매도금액'].append(df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity)
                    break
                elif len(dict['종목코드']) == 3: # 종목수 3종목으로 제한
                    break
        return pd.DataFrame(dict)
    else :
        return pd.DataFrame({'종목코드' : [], '매도주수' : [], '매도금액' : []})
        print("손실 종목이 없습니다.")

if __name__ == "__main__" :
    dic = {'종목코드' : [], '매도주수' : [], '매도금액' : []}

    st.set_page_config(layout = 'wide')
    st.title("매도주수 추천기")
    # accounting_select_box = st.selectbox("계좌번호", (['계좌1', '계좌2', '계좌3', '계좌4', '계좌5']))
    accounting_select_box = st.selectbox("계좌번호", (list(df['계좌번호'].unique())))
    money = st.text_input("손실 시켜야하는 금액을 입력하세요.", value = 1500000)
    exchange_rate_buffer = st.text_input("환율을 고려한 버퍼 금액을 입력하세요(음수).", value = -60000)
    st.write(f"과세표준 : {format(int(money), ',')}원")
    st.write(f"버퍼금액 : {format(int(exchange_rate_buffer), ',')}원")
    st.write(f"버퍼금액 적용 후 과세표준 : {format(int(money) + int(exchange_rate_buffer), ',')}원")
    st.write(f"절세 전 해외주식 양도세 : {format(round(int(money) * 0.22), ',')}원")
    TLH_result = tax_loss_harvesting(df, int(money), dict=dic, accounting_number=accounting_select_box, buffer=int(exchange_rate_buffer))
    # st.write(f"손실 금액 더한 후 과세표준: {format(money + TLH_result['매도금액'].sum(), ',')}원")
    st.write(f"절세 후 해외주식 양도세 : {format(round((int(money) + TLH_result['매도금액'].sum()) * 0.22), ',')}원")

    col1, col2 = st.columns(2)

    with col1 :
        st.write("<손실 종목 리스트>")
        st.write(df[df['계좌번호']==accounting_select_box].reset_index(drop=True))
    with col2 :
        st.write('<매도 추천 종목 리스트>')
        st.write(TLH_result)