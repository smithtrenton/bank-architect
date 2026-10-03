package com.pkoka5.ironmanbankarchitect.catalog;

import com.pkoka5.ironmanbankarchitect.analysis.BankAnalysis;
import com.pkoka5.ironmanbankarchitect.analysis.BankAnalysisRequest;
import com.pkoka5.ironmanbankarchitect.analysis.BankAnalysisStatus;
import com.pkoka5.ironmanbankarchitect.bank.BankItemSnapshot;
import com.pkoka5.ironmanbankarchitect.bank.BankSnapshot;
import com.pkoka5.ironmanbankarchitect.organize.BankLayoutOptions;
import com.pkoka5.ironmanbankarchitect.organize.BankLayoutPlan;
import com.pkoka5.ironmanbankarchitect.organize.BankPresets;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Optional;
import org.junit.Test;

import static org.junit.Assert.*;

public class CanonicalItemClassificationOverridesTest
{
	@Test
	public void missingResourceBlocksAnalysisWithoutPoisoningCatalogClasses()
	{
		assertUnavailable(getClass().getResourceAsStream("/missing-override-test.tsv"));
		assertTrue(CanonicalItemClassificationOverrides.find(29577).isPresent());
	}

	@Test
	public void duplicateIdBlocksAnalysisInsteadOfUsingAPartialTable()
	{
		assertUnavailable(stream("# schema=1\n1\tGEAR\tgear\n1\tTOOL\ttool\n"));
	}

	@Test
	public void malformedRowsBlockAnalysis()
	{
		assertUnavailable(stream("# schema=1\n# No rows\n"));
		for (String row : List.of("1\tGEAR", "no-id\tGEAR\tgear", "1\tNO_CATEGORY\tgear",
			"0\tGEAR\tgear", "1\tGEAR\t"))
		{
			assertUnavailable(stream("# schema=1\n" + row + "\n"));
		}
	}

	@Test
	public void schemaMustBeExactlyVersionOneWithoutAnnotations()
	{
		for (String header : List.of("# schema=10", "# schema=1garbage", "# schema=2",
			"# schema=1 annotation", ""))
		{
			assertUnavailable(stream(header + "\n1\tGEAR\tgear\n"));
		}
	}

	@Test
	public void reviewedJavelinsAndBarbedBoltsHaveAmmoClassificationWithoutPromotingComponents()
	{
		int[] ammoIds = {825, 826, 827, 828, 829, 830, 831, 832, 833, 834, 835, 836,
			5642, 5643, 5644, 5645, 5646, 5647, 5648, 5649, 5650, 5651, 5652, 5653,
			19484, 19486, 19488, 19490, 21318, 21320, 21322, 21324, 881};
		for (int itemId : ammoIds)
		{
			ItemClassificationRefiner.Classification classification =
				CanonicalItemClassificationOverrides.find(itemId).get();
			assertEquals("item " + itemId, ItemCategory.GEAR, classification.getCategory());
			assertEquals("item " + itemId, "ammo", classification.getSubcategory());
		}
		assertFalse("Barbed bolt tips remain a component", CanonicalItemClassificationOverrides.find(47).isPresent());
	}

	@Test
	public void exactUtilityDestinationsKeepIndependentRoleFacts()
	{
		for (int id : new int[]{32, 38, 594, 4522, 4524, 4537, 4539, 4700, 4701, 4702})
		{
			CatalogItem item = CompositeItemCatalog.DEFAULT.describeOrUnknown(id);
			assertEquals(ItemCategory.TOOL, item.getCategory());
			assertEquals("light-source", item.getSubcategory());
			assertTrue(item.hasTag("light-source"));
		}
		for (int id : new int[]{1436, 7936, 24704})
		{
			CatalogItem item = CompositeItemCatalog.DEFAULT.describeOrUnknown(id);
			assertEquals(ItemCategory.SKILLING, item.getCategory());
			assertEquals("raw-resource", item.getSubcategory());
			assertTrue(item.hasTag("runecrafting-input"));
		}
		assertEquals("rune-container", CompositeItemCatalog.DEFAULT.describeOrUnknown(24416).getSubcategory());
		assertEquals("rune", CompositeItemCatalog.DEFAULT.describeOrUnknown(24607).getSubcategory());
	}

	@Test
	public void maledictionShardsAreExactEquipmentUpgradeComponents()
	{
		for (int id : new int[]{11931, 11932, 11933})
		{
			ItemClassificationRefiner.Classification row = CanonicalItemClassificationOverrides.find(id).get();
			assertEquals(ItemCategory.UNIQUE, row.getCategory());
			assertEquals("equipment-upgrade", row.getSubcategory());
			assertTrue(CompositeItemCatalog.DEFAULT.describeOrUnknown(id).hasTag("recipe-material"));
		}
	}

	@Test
	public void goutTuberUsesFarmingClassificationWithoutChangingQuestSnapdragon()
	{
		ItemClassificationRefiner.Classification gout = CanonicalItemClassificationOverrides.find(6311).get();
		assertEquals(ItemCategory.FARMING, gout.getCategory());
		assertEquals("farming", gout.getSubcategory());
		ItemClassificationRefiner.Classification snapdragon = CanonicalItemClassificationOverrides.find(29538).get();
		assertEquals(ItemCategory.CLEANUP, snapdragon.getCategory());
		assertEquals("quest-item", snapdragon.getSubcategory());
	}

	@Test
	public void validTableClassifiesAndClosesItsStream()
	{
		boolean[] closed = {false};
		InputStream input = new ByteArrayInputStream(
			"# schema=1\n1\tGEAR\tgear\tReadable note\n".getBytes(StandardCharsets.UTF_8))
		{
			@Override
			public void close()
			{
				closed[0] = true;
			}
		};
		CanonicalItemClassificationOverrides table = new CanonicalItemClassificationOverrides(input);
		table.requireAvailable();
		assertEquals(ItemCategory.GEAR, table.lookup(1).get().getCategory());
		assertFalse(table.lookup(2).isPresent());
		assertTrue(closed[0]);
	}

	private static InputStream stream(String text)
	{
		return new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8));
	}

	private static void assertUnavailable(InputStream stream)
	{
		CanonicalItemClassificationOverrides table = new CanonicalItemClassificationOverrides(stream);
		ResourceItemRegistry registry = new ResourceItemRegistry(table);
		ItemCatalog catalog = new CompositeItemCatalog(StaticItemCatalog.INSTANCE, registry);
		// Even an item known to the first catalogue must not bypass the failed required table.
		assertThrows(CatalogUnavailableException.class, () -> catalog.findById(5297));
		assertThrows(CatalogUnavailableException.class, () -> table.lookup(1));
		for (List<BankItemSnapshot> items : List.of(Collections.<BankItemSnapshot>emptyList(),
			Collections.singletonList(new BankItemSnapshot(5297, 1, 0))))
		{
			BankAnalysisRequest request = new BankAnalysisRequest(new BankSnapshot(items),
				Collections.emptyMap(), Collections.emptyMap(), Collections.emptyMap(),
				BankLayoutPlan.defaultFor(BankPresets.IRONMAN), BankLayoutOptions.DEFAULTS);
			List<BankAnalysisStatus> statuses = new ArrayList<>();
			BankAnalysis analysis = new BankAnalysis(Runnable::run, Runnable::run,
				() -> Optional.of(request), statuses::add, catalog, BankPresets.IRONMAN);
			// Retrying remains a controlled failure, never NoClassDefFoundError or partial success.
			for (int attempt = 0; attempt < 2; attempt++)
			{
				analysis.analyzeBank();
				BankAnalysisStatus status = statuses.get(statuses.size() - 1);
				assertEquals(BankAnalysisStatus.Kind.FAILED, status.kind());
				assertEquals(CatalogUnavailableException.PLAYER_MESSAGE, status.catalogSummaryText());
				assertEquals(CatalogUnavailableException.PLAYER_MESSAGE, status.organizationPreviewText());
				assertFalse(status.catalogSummary().isPresent());
				assertFalse(status.organizationPreview().isPresent());
			}
			analysis.close();
		}
	}
}
