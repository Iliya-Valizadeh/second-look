# Glossary

Each technical term has a heading and one plain sentence. Link a term to its heading
the first time it appears in each file. `make check-docs` checks this.

## Baseline

A simple method, such as always guessing the most common answer, that a model must
beat to be worth using.

## Bootstrap

A way to see how much a number could change: draw many new samples from the test rows,
with repeats allowed, and compute the number again on each one.

## Confidence interval

A range around a measured number that shows how much the number could move if the
test were run again on new data.

## F1 score

One score that combines precision and recall. It is high only when both are high.

## Mean absolute error

The average size of a miss, in the same units as the thing being predicted. Lower is
better.

## Precision

Of all the flags a method raises, the share that point at something real. High
precision means few wrong flags.

## Recall

Of all the real cases, the share a method finds. High recall means few misses.
