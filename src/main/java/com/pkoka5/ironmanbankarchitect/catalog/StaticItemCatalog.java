package com.pkoka5.ironmanbankarchitect.catalog;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/** Verified exact-ID supplements and seed workflows, independent of generated cache names. */
public final class StaticItemCatalog implements ItemCatalog
{
	public static final StaticItemCatalog INSTANCE = new StaticItemCatalog();
	private final RequiredResource<Map<Integer, CatalogItem>> itemsById = new RequiredResource<>(
		"supplemental item catalog", () -> loadItems(StaticItemCatalog.class.getResourceAsStream("supplemental-items.tsv")));

	private StaticItemCatalog()
	{
	}

	@Override public void requireAvailable()
	{
		itemsById.get();
	}

	@Override public Optional<CatalogItem> findById(int itemId)
	{
		return Optional.ofNullable(itemsById.get().get(itemId));
	}

	public boolean containsId(int itemId)
	{
		return itemsById.get().containsKey(itemId);
	}

	public int size()
	{
		return itemsById.get().size();
	}

	public Set<Integer> itemIds()
	{
		return itemsById.get().keySet();
	}

	static Map<Integer, CatalogItem> loadItems(InputStream stream)
	{
		if (stream == null) throw new IllegalStateException("Missing supplemental item catalog");
		Map<Integer, CatalogItem> items = new LinkedHashMap<>();
		try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8)))
		{
			if (!"# schema=1".equals(reader.readLine())) throw new IllegalStateException("Invalid supplemental item schema");
			String line;
			while ((line = reader.readLine()) != null)
			{
				if (line.isEmpty() || line.startsWith("#")) continue;
				String[] fields = line.split("\\t", -1);
				if (fields.length != 6) throw new IllegalStateException("Invalid supplemental item row: " + line);
				int id = Integer.parseInt(fields[0]);
				ItemCategory category = ItemCategory.valueOf(fields[2]);
				Set<String> tags = fields[4].isEmpty() ? Collections.emptySet()
					: new LinkedHashSet<>(Arrays.asList(fields[4].split(",", -1)));
				if (category == ItemCategory.UNKNOWN || (!fields[4].isEmpty() && tags.size() != fields[4].split(",", -1).length)
					|| tags.stream().anyMatch(tag -> !tag.matches("[a-z][a-z0-9-]*")))
					throw new IllegalStateException("Invalid supplemental item roles: " + line);
				CatalogItem item = new CatalogItem(id, fields[1], category, fields[3], tags, fields[5].isEmpty() ? null : fields[5]);
				if (items.putIfAbsent(id, item) != null) throw new IllegalStateException("Duplicate supplemental item ID: " + id);
			}
		}
		catch (IOException | IllegalArgumentException ex)
		{
			throw new IllegalStateException("Cannot read supplemental item catalog", ex);
		}
		if (items.isEmpty()) throw new IllegalStateException("Empty supplemental item catalog");
		return Collections.unmodifiableMap(items);
	}
}
