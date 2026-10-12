#!/bin/bash
# Find useMemo without empty dependency array []
grep -r "useMemo(" application/src/ | grep -v '\[\]' | head -n 20
