## Summary

Describe what changed and why.

## Related Issues

- Closes #
- Related #

## Change Type

- [ ] Bug fix
- [ ] Enhancement
- [ ] New feature
- [ ] Breaking change
- [ ] Refactor
- [ ] Documentation update
- [ ] CI/workflow update

## Scope

- [ ] Installers (`install.sh`, `install.ps1`)
- [ ] CLI / pipeline commands
- [ ] Codebase Intelligence (daemon/activity/memory/search)
- [ ] Agent integrations (hooks/MCP/skills)
- [ ] Templates / rules / strategic planning
- [ ] Packaging/release
- [ ] Docs

## Risk and Compatibility

- Risk level: [ ] low [ ] medium [ ] high
- Backward compatibility impact:
- Migration or operator action required:

## Validation

List exactly what you ran and the result.

```bash
# Required
make check

# If installers were touched
pytest tests/test_install_scripts.py -v
```

## Checklist

- [ ] I read [CONTRIBUTING.md](CONTRIBUTING.md) and relevant project rules in `oak/constitution.md`
- [ ] `make check` passes locally
- [ ] I added or updated tests where behavior changed
- [ ] I updated docs for user-visible behavior/workflow changes
- [ ] I called out risks and compatibility impacts above
- [ ] I verified installer behavior if `install.sh` or `install.ps1` changed
