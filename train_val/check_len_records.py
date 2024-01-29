import pandas as pd

def extract_infos():
  df = pd.read_pickle('D1_test.pkl')
  lens = []
  avg = sum = 0

  for record in df.iterrows():
      len = record[1].iloc[7] - record[1].iloc[6]
      sum += len
      avg += 1
      lens.append(len)

  avg = round(sum / avg)

  with open('D1_test_len.txt', 'w') as f:
      f.write(f'sum: {sum}\navg: {avg}\n')

if __name__ == '__main__':
  extract_infos()