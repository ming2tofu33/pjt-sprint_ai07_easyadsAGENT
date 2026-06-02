# Temporary Reference Images

This project can load local-only reference templates for development without mixing unverified third-party images into the permanent seed catalog.

## Runtime Flag

Temporary references are disabled by default. Enable them only in local development:

```bash
EASYADS_ENABLE_TEMP_REFERENCES=true
```

Optional custom root:

```bash
EASYADS_TEMP_REFERENCE_ROOT=data/reference_templates/_temporary_unlicensed
```

## Image Drop Path

Put temporary images here:

```text
data/reference_templates/_temporary_unlicensed/2026-06-user-refs/
```

The local manifest is:

```text
data/reference_templates/_temporary_unlicensed/2026-06-user-refs/catalog.local.json
```

That folder is ignored by Git. Delete this one folder to remove the whole temporary set:

```bash
rm -rf data/reference_templates/_temporary_unlicensed/2026-06-user-refs
```

## Expected File Names

The current local manifest expects these files:

```text
watermelon-juice.png
lemonade.png
ube-latte.png
ube-croffle.png
americano.png
summer-sale.png
beer-promo.png
pork-belly.png
ramen.png
sandwich.png
chestnut-latte.png
samgyetang.png
donut.png
bibimbap.png
hair-salon.png
```

## Safety Notes

- Keep these files out of commits.
- Keep `metadata.temporary`, `metadata.copyright_status`, and `metadata.removal_group` in the manifest.
- Remove the folder or turn off `EASYADS_ENABLE_TEMP_REFERENCES` before release demos that should not include unverified assets.
