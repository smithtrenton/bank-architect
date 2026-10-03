package com.pkoka5.ironmanbankarchitect.organize.layout;

import java.util.HashSet;
import java.util.Set;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class ItemSetCatalogTest
{
	@Test
	public void compiledWorkbookCatalogHasReviewedCoverageWithoutCrossSetDuplicates()
	{
		assertDomain("gear", 37, 144);
		assertDomain("tools", 15, 83);
		assertDomain("cosmetics", 43, 173);
		assertEquals("Wyrmscraig villager robe top (A)", ItemSetCatalog.cosmeticFamilyOf(33884).get());
		assertEquals(ItemSetCatalog.cosmeticFamilyOf(33884), ItemSetCatalog.cosmeticFamilyOf(33905));
		assertEquals("Wyrmscraig villager robe top (B)", ItemSetCatalog.cosmeticFamilyOf(33950).get());
	}

	private static void assertDomain(String domain, int expectedSets, int expectedItems)
	{
		assertEquals(expectedSets, ItemSetCatalog.sets(domain).size());
		Set<Integer> itemIds = new HashSet<>();
		for (ItemSetCatalog.SetDefinition definition : ItemSetCatalog.sets(domain))
		{
			assertTrue(definition.getItemIds().size() >= 2);
			for (Integer itemId : definition.getItemIds())
			{
				assertTrue("duplicate item " + itemId + " in " + domain, itemIds.add(itemId));
			}
		}
		assertEquals(expectedItems, itemIds.size());
	}
}
