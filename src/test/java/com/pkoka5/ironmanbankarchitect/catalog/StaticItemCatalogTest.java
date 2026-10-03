package com.pkoka5.ironmanbankarchitect.catalog;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.pkoka5.ironmanbankarchitect.match.HardcodedSlotItemMappings;
import com.pkoka5.ironmanbankarchitect.match.SlotItemMapping;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import org.junit.Test;

public class StaticItemCatalogTest
{
	private static final List<Integer> VERIFIED_PHASE_B_ITEM_IDS = Arrays.asList(
		5297, 209, 259, 101, 221, 145, 147, 149
	);

	private static final List<String> VERIFIED_PHASE_B_SLOT_KEYS = Arrays.asList(
		"herblore.irit.seed",
		"herblore.irit.grimy",
		"herblore.irit.clean",
		"herblore.irit.unf",
		"herblore.irit.secondary",
		"herblore.super-attack.3",
		"herblore.super-attack.2",
		"herblore.super-attack.1"
	);

	@Test
	public void catalogFindsAllVerifiedPhaseBItemIds()
	{
		for (int itemId : VERIFIED_PHASE_B_ITEM_IDS)
		{
			assertTrue("expected catalog entry for item " + itemId, StaticItemCatalog.INSTANCE.findById(itemId).isPresent());
		}
	}

	@Test
	public void unknownIdReturnsUnknownSafely()
	{
		int unmappedItemId = 999999;

		assertFalse(StaticItemCatalog.INSTANCE.findById(unmappedItemId).isPresent());

		CatalogItem described = StaticItemCatalog.INSTANCE.describeOrUnknown(unmappedItemId);
		assertEquals(unmappedItemId, described.getItemId());
		assertEquals(ItemCategory.UNKNOWN, described.getCategory());
		assertEquals("unknown", described.getSubcategory());
		assertTrue(described.getTags().isEmpty());
		assertFalse(described.getWorkflowKey().isPresent());
	}

	@Test
	public void describeOrUnknownHandlesZeroWithoutThrowing()
	{
		CatalogItem described = StaticItemCatalog.INSTANCE.describeOrUnknown(0);

		assertEquals(0, described.getItemId());
		assertEquals(ItemCategory.UNKNOWN, described.getCategory());
	}

	@Test
	public void describeOrUnknownHandlesNegativeIdWithoutThrowing()
	{
		CatalogItem described = StaticItemCatalog.INSTANCE.describeOrUnknown(-1);

		assertEquals(-1, described.getItemId());
		assertEquals(ItemCategory.UNKNOWN, described.getCategory());
	}

	@Test
	public void describeOrUnknownHandlesIntegerMinValueWithoutThrowing()
	{
		CatalogItem described = StaticItemCatalog.INSTANCE.describeOrUnknown(Integer.MIN_VALUE);

		assertEquals(Integer.MIN_VALUE, described.getItemId());
		assertEquals(ItemCategory.UNKNOWN, described.getCategory());
	}

	@Test
	public void knownItemConstructionStillRejectsNonPositiveItemId()
	{
		assertThrowsIllegalArgument(() -> new CatalogItem(0, "Test item", ItemCategory.HERBLORE, "test", Collections.emptySet(), null));
		assertThrowsIllegalArgument(() -> new CatalogItem(-1, "Test item", ItemCategory.HERBLORE, "test", Collections.emptySet(), null));
	}

	@Test
	public void iritWorkflowCategoriesAndTagsAreCorrect()
	{
		assertCategoryAndTags(5297, ItemCategory.FARMING, "irit", "herb-seed");
		assertCategoryAndTags(209, ItemCategory.HERBLORE, "irit", "grimy");
		assertCategoryAndTags(259, ItemCategory.HERBLORE, "irit", "clean");
		assertCategoryAndTags(101, ItemCategory.HERBLORE, "irit", "unfinished-potion");
		assertCategoryAndTags(221, ItemCategory.HERBLORE, "secondary", "super-attack");
		assertCategoryAndTags(145, ItemCategory.POTION, "super-attack", "dose-3");
		assertCategoryAndTags(147, ItemCategory.POTION, "super-attack", "dose-2");
		assertCategoryAndTags(149, ItemCategory.POTION, "super-attack", "dose-1");
	}

	@Test
	public void superAttackFourIsNotPartOfPhaseBIritCatalogWorkflow()
	{
		// Super attack (4), item ID 2436, is reserved for a future Potion / Consumables / PvM
		// Supplies catalog area and must not appear in this Phase B Irit prep catalog.
		assertFalse(StaticItemCatalog.INSTANCE.findById(2436).isPresent());
	}

	@Test
	public void hardcodedSlotItemMappingIdsArePresentInCatalog()
	{
		for (String slotKey : VERIFIED_PHASE_B_SLOT_KEYS)
		{
			Optional<SlotItemMapping> mapping = HardcodedSlotItemMappings.forSlotKey(slotKey);
			assertTrue("expected a hardcoded mapping for " + slotKey, mapping.isPresent());

			int itemId = mapping.get().getItemId();
			assertTrue("expected catalog entry for mapped item " + itemId + " (" + slotKey + ")",
				StaticItemCatalog.INSTANCE.containsId(itemId));
		}
	}

	@Test
	public void noDuplicateItemIdsInStaticCatalog()
	{
		Set<Integer> uniqueIds = new HashSet<>(VERIFIED_PHASE_B_ITEM_IDS);
		uniqueIds.addAll(Arrays.asList(34024, 34401, 34428));
		assertTrue(StaticItemCatalog.INSTANCE.itemIds().containsAll(uniqueIds));
		assertEquals(351, StaticItemCatalog.INSTANCE.size());
		assertEquals(StaticItemCatalog.INSTANCE.size(), StaticItemCatalog.INSTANCE.itemIds().size());
	}

	@Test
	public void supplementalNecklacesHaveVerifiedCombatRoles()
	{
		assertCategoryAndTags(34401, ItemCategory.GEAR, "ranged-gear");
		assertCategoryAndTags(34428, ItemCategory.GEAR, "magic-gear", "spell-enhancement");
		assertEquals("Necklace of Fangs", StaticItemCatalog.INSTANCE.describeOrUnknown(34401).getDisplayName());
		assertEquals("Elemental amulet", StaticItemCatalog.INSTANCE.describeOrUnknown(34428).getDisplayName());
		assertEquals("neck", StaticItemCatalog.INSTANCE.describeOrUnknown(34428).getSubcategory());
	}

	@Test
	public void reviewedSupplementsPreserveFunctionalAndQuestStateBoundaries()
	{
		assertCategoryAndTags(34027, ItemCategory.GEAR, "area-damage");
		assertCategoryAndTags(34063, ItemCategory.GEAR, "snail-protection");
		assertCategoryAndTags(34407, ItemCategory.GEAR, "spell-enhancement");
		assertCategoryAndTags(34431, ItemCategory.CLUE, "clue-utility", "storage-option-menagerie");
		assertCategoryAndTags(34503, ItemCategory.CLUE, "pet-growth");
		assertFalse(StaticItemCatalog.INSTANCE.describeOrUnknown(34503).hasTag("clue-utility"));
		assertFalse(StaticItemCatalog.INSTANCE.describeOrUnknown(34503).hasTag("storage-option-menagerie"));
		assertCategoryAndTags(34030, ItemCategory.TOOL, "light-source");
		assertCategoryAndTags(34022, ItemCategory.SKILLING, "crafting-utility", "quest-use");
		assertCategoryAndTags(34575, ItemCategory.CLEANUP, "quest-puzzle");
		assertCategoryAndTags(34582, ItemCategory.CLEANUP, "quest-decoy");
		assertFalse(StaticItemCatalog.INSTANCE.describeOrUnknown(34582).hasTag("quest-use"));
		assertCategoryAndTags(34589, ItemCategory.CLUE, "musical-toy");
		assertCategoryAndTags(34077, ItemCategory.UNIQUE, "claimable-reward");
		assertCategoryAndTags(34207, ItemCategory.UNIQUE, "claimable-reward");
		assertEquals("cosmetic", StaticItemCatalog.INSTANCE.describeOrUnknown(33836).getSubcategory());
		for (int id : new int[]{33833, 34016, 34035, 34044, 34045, 34046, 34054, 34055, 34056, 34059, 34061, 34388, 34390, 34598, 34599, 34600})
			assertFalse("excluded bank item " + id, StaticItemCatalog.INSTANCE.containsId(id));
	}

	@Test
	public void supplementalResourceRejectsMissingMalformedAndDuplicateRecords()
	{
		for (String text : new String[]{"# schema=2\n", "# schema=1\n1\tshort\n",
			"# schema=1\n1\tTest\tGEAR\tneck\tinvalid tag\t\n",
			"# schema=1\n1\tTest\tGEAR\tneck\t\t\n1\tDuplicate\tGEAR\tneck\t\t\n"})
		{
			try
			{
				StaticItemCatalog.loadItems(new java.io.ByteArrayInputStream(text.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
				throw new AssertionError("expected invalid supplemental resource");
			}
			catch (IllegalStateException expected) { }
		}
		try
		{
			StaticItemCatalog.loadItems(null);
			throw new AssertionError("expected missing supplemental resource");
		}
		catch (IllegalStateException expected) { }
	}

	private static void assertThrowsIllegalArgument(Runnable action)
	{
		try
		{
			action.run();
			throw new AssertionError("expected IllegalArgumentException");
		}
		catch (IllegalArgumentException expected)
		{
			// expected
		}
	}

	private static void assertCategoryAndTags(int itemId, ItemCategory expectedCategory, String... expectedTags)
	{
		CatalogItem item = StaticItemCatalog.INSTANCE.findById(itemId)
			.orElseThrow(() -> new AssertionError("expected catalog entry for item " + itemId));

		assertEquals(expectedCategory, item.getCategory());
		for (String expectedTag : expectedTags)
		{
			assertTrue("expected item " + itemId + " to have tag " + expectedTag, item.hasTag(expectedTag));
		}
	}
}
