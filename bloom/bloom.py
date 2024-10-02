# -*- encoding: utf-8 -*-
"""
Этот модуль реализует вероятностную структуру данных Bloom filter и
Scalable bloom filter, который увеличивается в размере по мере добавления в него новых элементов,
не увеличивая при этом частоту ложных срабатываний error_rate.

Обязательно наличие библиотеки bitarray: http://pypi.python.org/pypi/bitarray/

    >>> from bloom import BloomFilter
    >>> f = BloomFilter(capacity=10000, error_rate=0.001)
    >>> for i in range_fn(0, f.capacity):
    ...     _ = f.add(i)
    ...
    >>> 0 in f
    True
    >>> f.capacity in f
    False
    >>> len(f) <= f.capacity
    True
    >>> (1.0 - (len(f) / float(f.capacity))) <= f.error_rate + 2e-18
    True

    >>> from bloom import ScalableBloomFilter
    >>> sbf = ScalableBloomFilter(mode=ScalableBloomFilter.SMALL_SET_GROWTH)
    >>> count = 10000
    >>> for i in range_fn(0, count):
    ...     _ = sbf.add(i)
    ...
    >>> sbf.capacity > count
    True
    >>> len(sbf) <= count
    True
    >>> (1.0 - (len(sbf) / float(count))) <= sbf.error_rate + 2e-18
    True

"""
from __future__ import absolute_import
import math
import hashlib
from bloom.utils import range_fn, is_string_io, running_python_3
from struct import unpack, pack, calcsize

try:
    import bitarray
except ImportError:
    raise ImportError('bloom requires bitarray >= 0.3.4')

__version__ = '1.0'
__author__  = "Daria Minina"

def make_hashfuncs(num_slices, num_bits):
    if num_bits >= (1 << 31):
        fmt_code, chunk_size = 'Q', 8
    elif num_bits >= (1 << 15):
        fmt_code, chunk_size = 'I', 4
    else:
        fmt_code, chunk_size = 'H', 2
    total_hash_bits = 8 * num_slices * chunk_size
    if total_hash_bits > 384:
        hashfn = hashlib.sha512
    elif total_hash_bits > 256:
        hashfn = hashlib.sha384
    elif total_hash_bits > 160:
        hashfn = hashlib.sha256
    elif total_hash_bits > 128:
        hashfn = hashlib.sha1
    else:
        hashfn = hashlib.md5
    fmt = fmt_code * (hashfn().digest_size // chunk_size)
    num_salts, extra = divmod(num_slices, len(fmt))
    if extra:
        num_salts += 1
    salts = tuple(hashfn(hashfn(pack('I', i)).digest()) for i in range_fn(num_salts))
    def _make_hashfuncs(key):
        if running_python_3:
            if isinstance(key, str):
                key = key.encode('utf-8')
            else:
                key = str(key).encode('utf-8')
        else:
            if isinstance(key, unicode):
                key = key.encode('utf-8')
            else:
                key = str(key)
        i = 0
        for salt in salts:
            h = salt.copy()
            h.update(key)
            for uint in unpack(fmt, h.digest()):
                yield uint % num_bits
                i += 1
                if i >= num_slices:
                    return

    return _make_hashfuncs


class BloomFilter(object):
    FILE_FMT = b'<dQQQQ'

    def __init__(self, capacity, error_rate=0.001):
        """
        Реализует вероятностную структуру данных

        capacity
            BloomFilter должен иметь возможность хранить не менее *capacity* элементов
            при сохранении не более *error_rate* вероятности ложноположительных срабатываний
        error_rate
            Определяет емкость фильтров. Вставка более чем capacity элементов 
            значительно увеличивает вероятность ложноположительных срабатываний.

        >>> b = BloomFilter(capacity=100000, error_rate=0.001)
        >>> b.add("test")
        False
        >>> "test" in b
        True
        """

        if not (0 < error_rate < 1):
            raise ValueError("Error_Rate must be between 0 and 1.")
        if not capacity > 0:
            raise ValueError("Capacity must be > 0")
        # дано M = num_bits, k = num_slices, P = error_rate, n = capacity
        #       k = log2(1/P)
        # решаем для m = bits_per_slice
        # n ~= M * ((ln(2) ** 2) / abs(ln(P)))
        # n ~= (k * m) * ((ln(2) ** 2) / abs(ln(P)))
        # m ~= n * abs(ln(P)) / (k * (ln(2) ** 2))
        num_slices = int(math.ceil(math.log(1.0 / error_rate, 2)))
        bits_per_slice = int(math.ceil(
            (capacity * abs(math.log(error_rate))) /
            (num_slices * (math.log(2) ** 2))))
        self._setup(error_rate, num_slices, bits_per_slice, capacity, 0)
        self.bitarray = bitarray.bitarray(self.num_bits, endian='little')
        self.bitarray.setall(False)

    def _setup(self, error_rate, num_slices, bits_per_slice, capacity, count):
        self.error_rate = error_rate
        self.num_slices = num_slices
        self.bits_per_slice = bits_per_slice
        self.capacity = capacity
        self.num_bits = num_slices * bits_per_slice
        self.count = count
        self.make_hashes = make_hashfuncs(self.num_slices, self.bits_per_slice)

    def __contains__(self, key):
        """Проверка наличия ключа в этом bloom filter

        >>> b = BloomFilter(capacity=100)
        >>> b.add("hello")
        False
        >>> "hello" in b
        True

        """
        bits_per_slice = self.bits_per_slice
        bitarray = self.bitarray
        hashes = self.make_hashes(key)
        offset = 0
        for k in hashes:
            if not bitarray[offset + k]:
                return False
            offset += bits_per_slice
        return True

    def __len__(self):
        """Возвращает количество ключей, которое содержит bloom filter"""
        return self.count

    def add(self, key, skip_check=False):
        """ Добавление ключа. Если ключ уже есть, то вовращает True. Иначе False.

        >>> b = BloomFilter(capacity=100)
        >>> b.add("hello")
        False
        >>> b.add("hello")
        True
        >>> b.count
        1

        """
        bitarray = self.bitarray
        bits_per_slice = self.bits_per_slice
        hashes = self.make_hashes(key)
        found_all_bits = True
        if self.count > self.capacity:
            raise IndexError("BloomFilter is at capacity")
        offset = 0
        for k in hashes:
            if not skip_check and found_all_bits and not bitarray[offset + k]:
                found_all_bits = False
            self.bitarray[offset + k] = True
            offset += bits_per_slice

        if skip_check:
            self.count += 1
            return False
        elif not found_all_bits:
            self.count += 1
            return False
        else:
            return True

    def copy(self):
        """Возвращает копию данного bloom filter.
        """
        new_filter = BloomFilter(self.capacity, self.error_rate)
        new_filter.bitarray = self.bitarray.copy()
        return new_filter

    def union(self, other):
        """ union два bitarray и создание нового bloom filter"""
        if self.capacity != other.capacity or \
            self.error_rate != other.error_rate:
            raise ValueError("Unioning filters requires both filters to have \
                both the same capacity and error rate")
        new_bloom = self.copy()
        new_bloom.bitarray = new_bloom.bitarray | other.bitarray
        return new_bloom

    def __or__(self, other):
        return self.union(other)

    def intersection(self, other):
        """ пересечение двух bitarrays и создание нового bloom filter """
        if self.capacity != other.capacity or \
            self.error_rate != other.error_rate:
            raise ValueError("Intersecting filters requires both filters to \
                have equal capacity and error rate")
        new_bloom = self.copy()
        new_bloom.bitarray = new_bloom.bitarray & other.bitarray
        return new_bloom

    def __and__(self, other):
        return self.intersection(other)

    def tofile(self, f):
        """Запись содержимого bloom filter в объект `f`."""
        f.write(pack(self.FILE_FMT, self.error_rate, self.num_slices,
                    self.bits_per_slice, self.capacity, self.count))
        (f.write(self.bitarray.tobytes()) if is_string_io(f)
        else self.bitarray.tofile(f))

    @classmethod
    def fromfile(cls, f, n=-1):
        """Чтение bloom filter из файла `f`. Если n > 0, то такое количество битов и прочтет."""
        headerlen = calcsize(cls.FILE_FMT)

        if 0 < n < headerlen:
            raise ValueError('n too small!')

        filter = cls(1)  # Bogus instantiation, we will `_setup'.
        filter._setup(*unpack(cls.FILE_FMT, f.read(headerlen)))
        filter.bitarray = bitarray.bitarray(endian='little')
        if n > 0:
            (filter.bitarray.frombytes(f.read(n-headerlen)) if is_string_io(f)
            else filter.bitarray.fromfile(f, n - headerlen))
        else:
            (filter.bitarray.frombytes(f.read()) if is_string_io(f)
            else filter.bitarray.fromfile(f))
        if filter.num_bits != filter.bitarray.length() and \
            (filter.num_bits + (8 - filter.num_bits % 8)
                != filter.bitarray.length()):
            raise ValueError('Bit length mismatch!')

        return filter

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['make_hashes']
        return d

    def __setstate__(self, d):
        self.__dict__.update(d)
        self.make_hashes = make_hashfuncs(self.num_slices, self.bits_per_slice)

class ScalableBloomFilter(object):
    SMALL_SET_GROWTH = 2 # медленнее, но ест меньше памяти
    LARGE_SET_GROWTH = 4 # быстрее, но ест больше памяти
    FILE_FMT = '<idQd'

    def __init__(self, initial_capacity=100, error_rate=0.001,
                mode=SMALL_SET_GROWTH):
        """
        Реализует вероятностную структуру данных, которая эффективно использует пространство,
        растет по мере добавления новых элементов, поддерживая при этом постоянный уровень ложных
        положительных результатов

        initial_capacity
            изначальная емкость фильтра

        error_rate
            error_rate фильтра, возвращающего ложные результаты. Это
            определяет capacity фильтров. Превышение capacity значительно
            увеличивает вероятность ложных результатов.
        
        mode
            может быть либо ScalableBloomFilter.SMALL_SET_GROWTH, либо
            ScalableBloomFilter.LARGE_SET_GROWTH. SMALL_SET_GROWTH медленнее,
            но использует меньше памяти. LARGE_SET_GROWTH быстрее, но потребляет
            памяти больше.

        >>> b = ScalableBloomFilter(initial_capacity=512, error_rate=0.001, \
                                    mode=ScalableBloomFilter.SMALL_SET_GROWTH)
        >>> b.add("test")
        False
        >>> "test" in b
        True
        >>> unicode_string = u'¡'
        >>> b.add(unicode_string)
        False
        >>> unicode_string in b
        True
        """
        if not error_rate or error_rate < 0:
            raise ValueError("Error_Rate must be a decimal less than 0.")
        self._setup(mode, 0.9, initial_capacity, error_rate)
        self.filters = []

    def _setup(self, mode, ratio, initial_capacity, error_rate):
        self.scale = mode
        self.ratio = ratio
        self.initial_capacity = initial_capacity
        self.error_rate = error_rate

    def __contains__(self, key):
        """Проверка наличия ключа в ScalableBloomFilter

        >>> b = ScalableBloomFilter(initial_capacity=100, error_rate=0.001, \
                                    mode=ScalableBloomFilter.SMALL_SET_GROWTH)
        >>> b.add("hello")
        False
        >>> "hello" in b
        True

        """
        for f in reversed(self.filters):
            if key in f:
                return True
        return False

    def add(self, key):
        """Добавление ключа. Если ключ уже есть, то вовращает True. Иначе False.

        >>> b = ScalableBloomFilter(initial_capacity=100, error_rate=0.001, \
                                    mode=ScalableBloomFilter.SMALL_SET_GROWTH)
        >>> b.add("hello")
        False
        >>> b.add("hello")
        True

        """
        if key in self:
            return True
        if not self.filters:
            filter = BloomFilter(
                capacity=self.initial_capacity,
                error_rate=self.error_rate * (1.0 - self.ratio))
            self.filters.append(filter)
        else:
            filter = self.filters[-1]
            if filter.count >= filter.capacity:
                filter = BloomFilter(
                    capacity=filter.capacity * self.scale,
                    error_rate=filter.error_rate * self.ratio)
                self.filters.append(filter)
        filter.add(key, skip_check=True)
        return False

    @property
    def capacity(self):
        """Возвращает итоговое capacity для всех фильтров в этом SBF"""
        return sum(f.capacity for f in self.filters)

    @property
    def count(self):
        return len(self)

    def tofile(self, f):
        """Сериализация ScalableBloomFilter в файл `f`."""
        f.write(pack(self.FILE_FMT, self.scale, self.ratio,
                    self.initial_capacity, self.error_rate))

        # Write #-of-filters
        f.write(pack(b'<l', len(self.filters)))

        if len(self.filters) > 0:
            headerpos = f.tell()
            headerfmt = b'<' + b'Q'*(len(self.filters))
            f.write(b'.' * calcsize(headerfmt))
            filter_sizes = []
            for filter in self.filters:
                begin = f.tell()
                filter.tofile(f)
                filter_sizes.append(f.tell() - begin)

            f.seek(headerpos)
            f.write(pack(headerfmt, *filter_sizes))

    @classmethod
    def fromfile(cls, f):
        """Десериализация ScalableBloomFilter в файл `f`."""
        filter = cls()
        filter._setup(*unpack(cls.FILE_FMT, f.read(calcsize(cls.FILE_FMT))))
        nfilters, = unpack(b'<l', f.read(calcsize(b'<l')))
        if nfilters > 0:
            header_fmt = b'<' + b'Q'*nfilters
            bytes = f.read(calcsize(header_fmt))
            filter_lengths = unpack(header_fmt, bytes)
            for fl in filter_lengths:
                filter.filters.append(BloomFilter.fromfile(f, fl))
        else:
            filter.filters = []

        return filter

    def __len__(self):
        """Возвращает количество объектов, которые хранятся в этом SBF"""
        return sum(f.count for f in self.filters)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
