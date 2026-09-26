"""Synthetic evaluation for second-look (docs/eval_plan.md).

This package lives outside `src/second_look` because it uses `random` and does file
I/O, which ADR 0001 forbids in the core engine. It calls the engine only through its
public functions (`second_look.importer`, `second_look.recurring`,
`second_look.duplicate`, `second_look.unusual`, `second_look.merchant`), the same way
the command line does.
"""
