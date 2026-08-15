# Tổng hai số

**Ý tưởng:** Đọc hai số nguyên $a$, $b$ và in ra $a+b$.

Độ phức tạp:

- Thời gian: $O(1)$.
- Bộ nhớ: $O(1)$.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long a, b;
    cin >> a >> b;
    cout << a + b << '\n';
    return 0;
}
```

