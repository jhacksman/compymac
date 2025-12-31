# Tool Availability Masks

Tool masks restrict which tools are available for specific phases or tasks.
This is a security primitive that reduces attack surface.

## Default Mask (all tools available)

AVAILABLE: Read, Edit, Write, glob, grep, bash, think, complete

## Planning Phase Mask

AVAILABLE: Read, glob, grep, think
BLOCKED: Edit, Write, bash, complete

## Untrusted Content Handling Mask

AVAILABLE: Read, grep, think
BLOCKED: Edit, Write, bash, complete, glob

## Verification Phase Mask

AVAILABLE: bash, Read, think, complete
BLOCKED: Edit, Write, glob, grep
