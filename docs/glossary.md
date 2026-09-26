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

## Content-Security-Policy (CSP)

A rule a web page sends to the browser that limits which addresses the page's own
code can load a script from or send a request to.

## F1 score

One score that combines precision and recall. It is high only when both are high.

## Mean absolute error

The average size of a miss, in the same units as the thing being predicted. Lower is
better.

## Modified z-score

A score that shows how far a value sits from the middle of a group of values. It is
built so that one far-off value in the group cannot pull the score of the value being
checked back down.

## Precision

Of all the flags a method raises, the share that point at something real. High
precision means few wrong flags.

## Pyodide

A build of Python that runs inside a web browser, so a page can run Python code with
nothing sent to a server.

## Recall

Of all the real cases, the share a method finds. High recall means few misses.
