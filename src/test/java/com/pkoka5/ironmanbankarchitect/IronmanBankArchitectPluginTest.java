package com.pkoka5.ironmanbankarchitect;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.assertFalse;

import com.pkoka5.ironmanbankarchitect.organize.*;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

import net.runelite.client.RuneLite;
import net.runelite.client.externalplugins.ExternalPluginManager;
import org.junit.Test;

public class IronmanBankArchitectPluginTest
{
	// loadBuiltin is a generic varargs method; the array creation warning at
	// the call site is inherent to RuneLite's plugin test launcher template.
	@SuppressWarnings("unchecked")
	public static void main(String[] args) throws Exception
	{
		ExternalPluginManager.loadBuiltin(IronmanBankArchitectPlugin.class);
		RuneLite.main(args);
	}

	@Test
	public void pluginNameIsDefined()
	{
		assertEquals("Bank Architect", IronmanBankArchitectPlugin.PLUGIN_NAME);
	}

	@Test
	public void correctionsReadTheCurrentConfigurationProfile()
	{
		TestConfig config = new TestConfig();
		IronmanBankArchitectPlugin plugin = new IronmanBankArchitectPlugin();
		plugin.config = config;
		config.setCategoryOverrides("995=resources");
		plugin.applyCategoryOverride(209, "Grimy irit", "resources");
		config.setCategoryOverrides("556=herblore");
		plugin.applyCategoryOverride(257, "Ranarr weed", "resources");
		assertTrue(config.categoryOverrides().contains("556=herblore"));
		assertTrue(config.categoryOverrides().contains("257=resources"));
		assertFalse(config.categoryOverrides().contains("995=resources"));
		assertFalse(config.categoryOverrides().contains("209=resources"));
	}

	@Test
	public void initialDefaultOrdersSurviveSavingAndSelectingAnotherProfile()
	{
		TestConfig config = new TestConfig();
		config.setBlueprintOrdersByProfile("~v1|0:995,556");
		String blocks = BlockArrangements.EMPTY.withTag("currency", Arrays.asList("coins", "tokens")).serialize();
		config.setBlockOrders(blocks);
		IronmanBankArchitectPlugin plugin = new IronmanBankArchitectPlugin();
		plugin.config = config;
		BankLayoutModel model = plugin.bankLayoutModel();
		assertTrue(model.options().itemOrders().hasTab(0));
		model.saveProfile("Custom", BankLayoutPlan.defaultFor(BankPresets.IRONMAN));
		model.selectProfile(BankLayoutProfiles.DEFAULT_NAME);
		assertTrue(model.options().itemOrders().hasTab(0));
		assertEquals(blocks, config.blockOrders());
		assertEquals(BankLayoutProfiles.DEFAULT_NAME, config.activeLayoutProfile());
	}

	private static final class TestConfig implements IronmanBankArchitectConfig
	{
		private final Map<String, String> strings = new HashMap<>();
		@Override public void setAlchPile(boolean alchPile) {}
		@Override public void setGearLayout(GearLayout gearLayout) {}
		@Override public void setUtilitiesLayout(TabOrder utilitiesLayout) {}
		@Override public void setToolsLayout(TabOrder toolsLayout) {}
		@Override public void setResourcesLayout(TabOrder resourcesLayout) {}
		@Override public void setCluesLayout(TabOrder cluesLayout) {}
		@Override public void setKeepDoseRows(boolean keepDoseRows) {}
		@Override public void setFillHerbloreRows(boolean fillHerbloreRows) {}
		@Override public String categoryOverrides() { return strings.getOrDefault("categoryOverrides", ""); }
		@Override public void setCategoryOverrides(String serialized) { strings.put("categoryOverrides", serialized); }
		@Override public String tabOrder() { return strings.getOrDefault("tabOrder", ""); }
		@Override public void setTabOrder(String serialized) { strings.put("tabOrder", serialized); }
		@Override public String blockOrders() { return strings.getOrDefault("blockOrders", ""); }
		@Override public void setBlockOrders(String serialized) { strings.put("blockOrders", serialized); }
		@Override public String blockOrdersByProfile() { return strings.getOrDefault("blockOrdersByProfile", ""); }
		@Override public void setBlockOrdersByProfile(String serialized) { strings.put("blockOrdersByProfile", serialized); }
		@Override public String blueprintOrdersByProfile() { return strings.getOrDefault("blueprintOrdersByProfile", ""); }
		@Override public void setBlueprintOrdersByProfile(String serialized) { strings.put("blueprintOrdersByProfile", serialized); }
		@Override public String layoutProfiles() { return strings.getOrDefault("layoutProfiles", ""); }
		@Override public void setLayoutProfiles(String serialized) { strings.put("layoutProfiles", serialized); }
		@Override public String activeLayoutProfile() { return strings.getOrDefault("activeLayoutProfile", ""); }
		@Override public void setActiveLayoutProfile(String name) { strings.put("activeLayoutProfile", name); }
		@Override public String lastSeenRelease() { return strings.getOrDefault("lastSeenRelease", ""); }
		@Override public void setLastSeenRelease(String releaseId) { strings.put("lastSeenRelease", releaseId); }
	}

}
