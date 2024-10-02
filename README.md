# Тестирование работы разновидностей bloom filters

Перед разбором алгоритма предлагаем пройти инструкцию по настройке `python` и библиотек для дальнейшего запуска приложения.

### Создайте виртуальное окружение (Python >= 3.8.1)

```
python -m venv venv
```

### Активируйте виртуальное окружение

```
source venv/bin/activate
```

### Загрузите нужные библиотеки

```
pip install -r requirements.txt
```

### Результаты 

``bloom`` — это модуль, который включает структуру данных `bloom filter` вместе с
реализацией `Scalable bloom filter` (Almeida, C. Baquero, N. Preguiça, D. Hutchison, Scalable Bloom Filters,
(GLOBECOM 2007), IEEE, 2007)

- **`Bloom filters`** используются, если мы примерно понимаем, какое количество битов нужно выделить заранее для хранения всего набора. 

- **`Scalable bloom filters`** позволяют битам bloom filter расти в зависимости от вероятности ложного срабатывания и размера.

Фильтр "полный", когда он заполнен: 

M * ((ln 2 ^ 2) / abs(ln p)), 

где M — количество битов, а p — вероятность ложного срабатывания. 

Когда емкость достигнута, создается новый фильтр, экспоненциально больший, чем предыдущий, с более низкой вероятностью ложных срабатываний и большим количеством хэш-функций.

.. code-block:: python

    >>> from bloom import BloomFilter
    >>> f = BloomFilter(capacity=1000, error_rate=0.001)
    >>> [f.add(x) for x in range(10)]
    [False, False, False, False, False, False, False, False, False, False]
    >>> all([(x in f) for x in range(10)])
    True
    >>> 10 in f
    False
    >>> 5 in f
    True
    >>> f = BloomFilter(capacity=1000, error_rate=0.001)
    >>> for i in xrange(0, f.capacity):
    ...     _ = f.add(i)
    >>> (1.0 - (len(f) / float(f.capacity))) <= f.error_rate + 2e-18
    True

    >>> from bloom import ScalableBloomFilter
    >>> sbf = ScalableBloomFilter(mode=ScalableBloomFilter.SMALL_SET_GROWTH)
    >>> count = 10000
    >>> for i in xrange(0, count):
    ...     _ = sbf.add(i)
    ...
    >>> (1.0 - (len(sbf) / float(count))) <= sbf.error_rate + 2e-18
    True

Результаты бенчмарков:


Для `Bloom filter`:
```
0.328 seconds to add to capacity,  305294.96 entries/second
Number of Filter Bits: 479256
Number of slices: 4
Bits per slice: 119814
------
Fraction of 1 bits at capacity: 0.566
0.252 seconds to check false positives,  397415.19 checks/second
Requested FP rate: 0.1000
Experimental false positive rate: 0.1048
Projected FP rate (Goel/Gupta): 0.102603
```

Для `Scalable bloom filter`:

```
0.798 seconds to add to capacity,  125347.20 entries/second
0.292 seconds to check false positives,  342620.67 checks/second
Requested FP rate: 0.1000
Experimental false positive rate: 0.0099
Final capacity:  100000
Count:  99814
```