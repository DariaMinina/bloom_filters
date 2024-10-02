#!/usr/bin/env python
#
"""Тест работы BloomFilter при заданных capacity и error rate."""
import sys
from bloom import ScalableBloomFilter
import bitarray, math, time
from bloom.utils import range_fn


def main(initial_capacity=100000, request_error_rate=0.1, mode=ScalableBloomFilter.SMALL_SET_GROWTH):
    f = ScalableBloomFilter(initial_capacity=initial_capacity, error_rate=request_error_rate, mode=mode)
    assert (initial_capacity == f.initial_capacity)
    start = time.time()
    for i in range_fn(0, f.initial_capacity):
        f.add(i)
    end = time.time()
    print("{:5.3f} seconds to add to capacity, {:10.2f} entries/second".format(
            end - start, f.initial_capacity / (end - start)))
    # oneBits = f.count(True)
    # zeroBits = f.count(False)
    # print("Number of 1 bits:", oneBits)
    # print("Number of 0 bits:", zeroBits)
    # print("Number of Filter Bits:", f.num_bits)
    # print("Number of slices:", f.num_slices)
    # print("Bits per slice:", f.bits_per_slice)
    # print("------")
    # print("Fraction of 1 bits at capacity: {:5.3f}".format(
    #         oneBits / float(f.num_bits)))
    # Look for false positives and measure the actual fp rate
    trials = f.initial_capacity
    fp = 0
    start = time.time()
    for i in range_fn(f.initial_capacity, f.initial_capacity + trials + 1):
        if i in f:
            fp += 1
    end = time.time()
    print(("{:5.3f} seconds to check false positives, "
        "{:10.2f} checks/second".format(end - start, trials / (end - start))))
    print("Requested FP rate: {:2.4f}".format(request_error_rate))
    print("Experimental false positive rate: {:2.4f}".format(fp / float(trials)))
    print("Final capacity: ", f.capacity)
    print("Count: ", f.count)
    # # Compute theoretical fp max (Goel/Gupta)
    # k = f.num_slices
    # m = f.num_bits
    # n = f.capacity
    # fp_theory = math.pow((1 - math.exp(-k * (n + 0.5) / (m - 1))), k)
    # print("Projected FP rate (Goel/Gupta): {:2.6f}".format(fp_theory))

if __name__ == '__main__' :
    status = main()
    sys.exit(status)
