#!/usr/bin/env python
# coding=utf8
# Nerd Fonts Version: 2.1.0
# script version: FH_3.2

VERSION = "2.1.0"
PROJECT_NAME = "Nerd Fonts"
PROJECT_NAME_ABBR = "NF"
PROJECT_NAME_SING = PROJECT_NAME[:-1]

import sys
try:
	import psMat
except ImportError:
	sys.exit(PROJECT_NAME + ": FontForge module is probably not installed. "
	"[See: http://designwithfontforge.com/en-US/Installing_Fontforge.html]")
from re import match
from os.path import splitext, dirname, abspath, isdir, isfile, join
from os import makedirs, listdir
from argparse import RawTextHelpFormatter, ArgumentParser
import errno
import subprocess
import json
try:
	from configparser import ConfigParser
except ImportError:
	sys.exit(PROJECT_NAME +
	": configparser module is probably not installed. Try `pip install configparser` or equivalent"
									)
try:
	import fontforge
except ImportError:
	sys.exit(PROJECT_NAME + (
	": FontForge module could not be loaded. Try installing fontforge python bindings "
	"[e.g. on Linux Debian or Ubuntu: `sudo apt install fontforge python-fontforge`]"
	))


class FontPatcher:
	def __init__(self, args, symFontArgs):
		self.args = args # class 'argparse.Namespace'
		self.symFontArgs = symFontArgs
		self.sourceFont = None # class 'fontforge.font'
		# For compatibility with the rest of nerdfonts we dont want to keep the
		# encoding positions for the following
		self.octiconsExactEncodingPosition = True
		self.fontlinuxExactEncodingPosition = True
		if args.compat:
			self.octiconsExactEncodingPosition = False
			self.fontlinuxExactEncodingPosition = False
		self.patchSet = None # class 'list'
		self.fontDim = None # class 'dict'
		self.onlybitmaps = 0
		self.extension = ""
		self.config = ConfigParser(empty_lines_in_values=False, allow_no_value=True)
		self.sourceFont = fontforge.open(self.args.font)
		self.setupFontNames()
		self.removeLigatures()
		makeSurePathExists(self.args.outputdir)
		self.checkPositionConflicts()
		self.setupPatchSet()
		self.setupLineDimensions()
		self.getSourceFontDimensions()
		self.sourceFont.encoding = 'UnicodeFull' # Update the font encoding to
		# ensure that the Unicode glyphs are available
		self.onlybitmaps = self.sourceFont.onlybitmaps # Fetch this property
		# before adding outlines. NOTE self.onlybitmaps initialized and never used
		if self.args.extension == "":
			self.extension = splitext(self.sourceFont.path)[1]
		else:
			self.extension = '.' + self.args.extension

	def patch(self):
		if self.args.single:
			# Force width to be equal on all glyphs to ensure the font is
			# considered monospaced on Windows.
			# This needs to be done on all characters, as some information
			# seems to be lost from the original font file.
			self.setSourceFontGlyphWidths()

		# Prevent opening and closing the fontforge font. Makes things faster when patching
		# multiple ranges using the same symbol font.
		previousSymbolFilename = ""
		symfont = None

		for patch in self.patchSet:
			if patch['Enabled']:
				if previousSymbolFilename != patch['Filename']:
					# We have a new symbol font, so close the previous one if it exists
					if symfont:
						symfont.close()
						symfont = None
					symfont = fontforge.open(__dir__ + "/src/glyphs/" + patch['Filename'])

					# Match the symbol font size to the source font size
					symfont.em = self.sourceFont.em
					previousSymbolFilename = patch['Filename']

				# If patch table doesn't include a source start and end, re-use
				# the symbol font values
				srcStart = patch['SrcStart']
				srcEnd = patch['SrcEnd']
				if not srcStart:
					srcStart = patch['SymStart']
				if not srcEnd:
					srcEnd = patch['SymEnd']
				self.copyGlyphs(srcStart, srcEnd, symfont, patch['SymStart'],
				patch['SymEnd'], patch['Exact'], patch['ScaleGlyph'], patch['Name'],
				patch['Attributes'])

		if symfont:
			symfont.close()
		print("\nDone with Patch Sets, generating font...")

		# the `PfEd-comments` flag is required for Fontforge to save '.comment' and '.fontlog'.
		self.sourceFont.generate(
		self.args.outputdir + "/" + self.sourceFont.fullname + self.extension,
		flags=('opentype', 'PfEd-comments'))
		print("\nGenerated: {}".format(self.sourceFont.fullname))

		if self.args.postprocess:
			subprocess.call([
			self.args.postprocess,
			self.args.outputdir + "/" + self.sourceFont.fullname + self.extension])
			print("\nPost Processed: {}".format(self.sourceFont.fullname))

	def setupFontNames(self):
		verboseAdditionalFontNameSuffix = " " + PROJECT_NAME_SING
		if self.args.windows: # attempt to shorten here on the additional name BEFORE trimming later
			additionalFontNameSuffix = " " + PROJECT_NAME_ABBR
		else:
			additionalFontNameSuffix = verboseAdditionalFontNameSuffix
		if not self.args.complete and not self.args.compat:
			# NOTE not all symbol fonts have appended their suffix here
			if self.args.fontawesome:
				additionalFontNameSuffix += " A"
				verboseAdditionalFontNameSuffix += " Plus Font Awesome"
			if self.args.fontawesomeextension:
				additionalFontNameSuffix += " AE"
				verboseAdditionalFontNameSuffix += " Plus Font Awesome Extension"
			if self.args.octicons:
				additionalFontNameSuffix += " O"
				verboseAdditionalFontNameSuffix += " Plus Octicons"
			if self.args.powersymbols:
				additionalFontNameSuffix += " PS"
				verboseAdditionalFontNameSuffix += " Plus Power Symbols"
			if self.args.pomicons:
				additionalFontNameSuffix += " P"
				verboseAdditionalFontNameSuffix += " Plus Pomicons"
			if self.args.fontlinux:
				additionalFontNameSuffix += " L"
				verboseAdditionalFontNameSuffix += " Plus Font Logos (Font Linux)"
			if self.args.material:
				additionalFontNameSuffix += " MDI"
				verboseAdditionalFontNameSuffix += " Plus Material Design Icons"
			if self.args.weather:
				additionalFontNameSuffix += " WEA"
				verboseAdditionalFontNameSuffix += " Plus Weather Icons"

		# if all source glyphs included simplify the name
		else:
			additionalFontNameSuffix = " " + PROJECT_NAME_SING + " Complete"
			verboseAdditionalFontNameSuffix = " " + PROJECT_NAME_SING + " Complete"

		# add mono signifier to end of name
		if self.args.single:
			additionalFontNameSuffix += " M"
			verboseAdditionalFontNameSuffix += " Mono"

		# basically split the font name around the dash "-" to get the fontname and the style (e.g. Bold)
		# this does not seem very reliable so only use the style here as a fallback if the font does not
		# have an internal style defined (in sfnt_names)
		# using '([^-]*?)' to get the item before the first dash "-"
		# using '([^-]*(?!.*-))' to get the item after the last dash "-"
		fontname, fallbackStyle = match("^([^-]*).*?([^-]*(?!.*-))$",
		self.sourceFont.fontname).groups()

		# dont trust 'sourceFont.familyname'
		familyname = fontname

		# fullname (filename) can always use long/verbose font name, even in windows
		fullname = self.sourceFont.fullname + verboseAdditionalFontNameSuffix
		fontname = fontname + additionalFontNameSuffix.replace(" ", "")

		# let us try to get the 'style' from the font info in sfnt_names and fallback to the
		# parse fontname if it fails:
		try:
			# search tuple:
			subFamilyTupleIndex = [x[1]
			for x in self.sourceFont.sfnt_names].index("SubFamily")

			# String ID is at the second index in the Tuple lists
			sfntNamesStringIDIndex = 2

			# now we have the correct item:
			subFamily = self.sourceFont.sfnt_names[subFamilyTupleIndex][
			sfntNamesStringIDIndex]
		except IndexError:
			sys.stderr.write(
			"{}: Could not find 'SubFamily' for given font, falling back to parsed fontname\n"
			.format(PROJECT_NAME))
			subFamily = fallbackStyle

		# some fonts have inaccurate 'SubFamily', if it is Regular let us trust the filename more:
		if subFamily == "Regular":
			subFamily = fallbackStyle
		if self.args.windows:
			maxFamilyLength = 31
			maxFontLength = maxFamilyLength - len('-' + subFamily)
			familyname += " " + PROJECT_NAME_ABBR
			fullname += " Windows Compatible"

			# now make sure less than 32 characters name length
			if len(fontname) > maxFontLength:
				fontname = fontname[:maxFontLength]
			if len(familyname) > maxFamilyLength:
				familyname = familyname[:maxFamilyLength]
		else:
			familyname += " " + PROJECT_NAME_SING
			if self.args.single:
				familyname += " Mono"

		# Don't truncate the subfamily to keep fontname unique.  MacOS treats fonts with
		# the same name as the same font, even if subFamily is different.
		fontname += '-' + subFamily

		# rename font
		#
		# comply with SIL Open Font License (OFL)
		reservedFontNameReplacements = {
		'source': 'sauce', 'Source': 'Sauce', 'hermit': 'hurmit', 'Hermit': 'Hurmit',
		'hasklig': 'hasklug', 'Hasklig': 'Hasklug', 'Share': 'Shure',
		'share': 'shure', 'IBMPlex': 'Blex', 'ibmplex': 'blex', 'IBM-Plex': 'Blex',
		'IBM Plex': 'Blex', 'terminus': 'terminess', 'Terminus': 'Terminess',
		'liberation': 'literation', 'Liberation': 'Literation',
		'iAWriter': 'iMWriting', 'iA Writer': 'iM Writing',
		'iA-Writer': 'iM-Writing', 'Anka/Coder': 'AnaConder'}

		# remove overly verbose font names
		# particularly regarding Powerline sourced Fonts (https://github.com/powerline/fonts)
		additionalFontNameReplacements = {'for Powerline': '', 'ForPowerline': ''}

		additionalFontNameReplacements2 = {'Powerline': ''}

		projectInfo = ("Patched with '" + PROJECT_NAME +
		" Patcher' (https://github.com/ryanoasis/nerd-fonts)\n\n"
		"* Website: https://www.nerdfonts.com\n"
		"* Version: " + VERSION + "\n"
		"* Development Website: https://github.com/ryanoasis/nerd-fonts\n"
		"* Changelog: https://github.com/ryanoasis/nerd-fonts/blob/master/changelog.md"
																)

		familyname = replaceFontName(familyname, reservedFontNameReplacements)
		fullname = replaceFontName(fullname, reservedFontNameReplacements)
		fontname = replaceFontName(fontname, reservedFontNameReplacements)
		familyname = replaceFontName(familyname, additionalFontNameReplacements)
		fullname = replaceFontName(fullname, additionalFontNameReplacements)
		fontname = replaceFontName(fontname, additionalFontNameReplacements)
		familyname = replaceFontName(familyname, additionalFontNameReplacements2)
		fullname = replaceFontName(fullname, additionalFontNameReplacements2)
		fontname = replaceFontName(fontname, additionalFontNameReplacements2)

		# replace any extra whitespace characters:
		self.sourceFont.familyname = " ".join(familyname.split())
		self.sourceFont.fullname = " ".join(fullname.split())
		self.sourceFont.fontname = " ".join(fontname.split())

		self.sourceFont.appendSFNTName('English (US)', 'Preferred Family',
		self.sourceFont.familyname)
		self.sourceFont.appendSFNTName('English (US)', 'Family',
		self.sourceFont.familyname)
		self.sourceFont.appendSFNTName('English (US)', 'Compatible Full',
		self.sourceFont.fullname)
		self.sourceFont.appendSFNTName('English (US)', 'SubFamily', subFamily)
		self.sourceFont.comment = projectInfo
		self.sourceFont.fontlog = projectInfo

		# TODO version not being set for all font types (e.g. ttf)
		# print("Version was {}".format(sourceFont.version))
		self.sourceFont.version += ";" + PROJECT_NAME + " " + VERSION
		# print("Version now is {}".format(sourceFont.version))

	def removeLigatures(self):
		""" let's deal with ligatures (mostly for monospaced fonts) """
		if self.args.configfile and self.config.read(self.args.configfile):
			if self.args.removeligatures:
				print("Removing ligatures from configfile `Subtables` section")
				ligatureSubtables = json.loads(self.config.get("Subtables", "ligatures"))
				for subtable in ligatureSubtables:
					print("Removing subtable:", subtable)
					try:
						self.sourceFont.removeLookupSubtable(subtable)
						print("Successfully removed subtable:", subtable)
					except Exception:
						print("Failed to remove subtable:", subtable)
			elif self.args.removeligatures:
				print("Unable to read configfile, unable to remove ligatures")
			else:
				print("No configfile given, skipping configfile related actions")

	def checkPositionConflicts(self):
		""" Prevent glyph encoding position conflicts between glyph sets """
		if self.args.fontawesome and self.args.octicons:
			self.octiconsExactEncodingPosition = False
		if self.args.fontawesome or self.args.octicons:
			self.fontlinuxExactEncodingPosition = False

	def setupPatchSet(self):
		""" Creates list of dicts to with instructions on copying glyphs from
		each symbol font into self.sourceFont """
		# Supported params: overlap | careful
		# Powerline dividers
		symAttrPowerline = {
		'default': {'align': 'c', 'valign': 'c', 'stretch': 'pa', 'params': ''},

		# Arrow tips
		0xe0b0: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0b1: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0b2: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0b3: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy', 'params': {'overlap': 0.02}},

		# Rounded arcs
		0xe0b4: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.01}}, 0xe0b5: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.01}}, 0xe0b6: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy', 'params': {'overlap': 0.01}},
		0xe0b7: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy', 'params': {'overlap': 0.01}},

		# Bottom Triangles
		0xe0b8: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0b9: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0ba: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0bb: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy', 'params': {'overlap': 0.02}},

		# Top Triangles
		0xe0bc: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0bd: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0be: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0bf: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy', 'params': {'overlap': 0.02}},

		# Flames
		0xe0c0: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.01}}, 0xe0c1: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.01}}, 0xe0c2: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.01}}, 0xe0c3: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy', 'params': {'overlap': 0.01}},

		# Small squares
		0xe0c4: {'align': 'l', 'valign': 'c', 'stretch': 'xy', 'params': ''},
		0xe0c5: {'align': 'r', 'valign': 'c', 'stretch': 'xy', 'params': ''},

		# Bigger squares
		0xe0c6: {'align': 'l', 'valign': 'c', 'stretch': 'xy', 'params': ''},
		0xe0c7: {'align': 'r', 'valign': 'c', 'stretch': 'xy', 'params': ''},

		# Waveform
		0xe0c8: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy', 'params': {'overlap': 0.01}},

		# Hexagons
		0xe0cc: {'align': 'l', 'valign': 'c', 'stretch': 'xy', 'params': ''},
		0xe0cd: {'align': 'l', 'valign': 'c', 'stretch': 'xy', 'params': ''},

		# Legos
		0xe0ce: {'align': 'l', 'valign': 'c', 'stretch': 'xy', 'params': ''},
		0xe0cf: {'align': 'c', 'valign': 'c', 'stretch': 'xy',
		'params': ''}, 0xe0d1: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy', 'params': {'overlap': 0.02}},

		# Top and bottom trapezoid
		0xe0d2: {
		'align': 'l', 'valign': 'c', 'stretch': 'xy',
		'params': {'overlap': 0.02}}, 0xe0d4: {
		'align': 'r', 'valign': 'c', 'stretch': 'xy', 'params': {'overlap': 0.02}}}

		symAttrDefault = {
		# 'pa' == preserve aspect ratio
		'default': {'align': 'c', 'valign': 'c', 'stretch': 'pa', 'params': ''}}

		symAttrFontA = {
		# 'pa' == preserve aspect ratio
		'default': {'align': 'c', 'valign': 'c', 'stretch': 'pa', 'params': ''},

		# Don't center these arrows vertically
		0xf0dc: {'align': 'c', 'valign': '', 'stretch': 'pa', 'params': ''},
		0xf0dd: {'align': 'c', 'valign': '', 'stretch': 'pa', 'params': ''},
		0xf0de: {'align': 'c', 'valign': '', 'stretch': 'pa', 'params': ''}}

		customAttr = {
		# 'pa' == preserve aspect ratio
		'default': {'align': 'c', 'valign': '', 'stretch': '', 'params': ''}}

		# Most glyphs we want to maximize during the scale.  However, there are some
		# that need to be small or stay relative in size to each other.
		# The following list are those glyphs.  A tuple represents a range.
		deviScaleList = {'ScaleGlyph': 0xE60E, 'GlyphsToScale': [(0xe6bd, 0xe6c3)]}
		fontAScaleList = {
		'ScaleGlyph': 0xF17A, 'GlyphsToScale': [
		0xf005, 0xf006, (0xf026, 0xf028), 0xf02b, 0xf02c, (0xf031, 0xf035),
		(0xf044, 0xf054), (0xf060, 0xf063), 0xf077, 0xf078, 0xf07d, 0xf07e, 0xf089,
		(0xf0d7, 0xf0da), (0xf0dc, 0xf0de), (0xf100, 0xf107), 0xf141, 0xf142,
		(0xf153, 0xf15a), (0xf175, 0xf178), 0xf182, 0xf183, (0xf221, 0xf22d),
		(0xf255, 0xf25b)]}
		octiScaleList = {
		'ScaleGlyph': 0xF02E, 'GlyphsToScale': [(0xf03d, 0xf040), 0xf044,
		(0xf051, 0xf053), 0xf05a, 0xf05b, 0xf071, 0xf078, (0xf09f, 0xf0aa), 0xf0ca]}

		# Define the character ranges
		# Symbol font ranges
		# yapf: disable
		self.patchSet = [
		{'Enabled': True, 'Name': "Seti-UI + Custom",
		'Filename': "original-source.otf", 'Exact': False, 'SymStart': 0xE4FA,
		'SymEnd': 0xE52E, 'SrcStart': 0xE5FA, 'SrcEnd': 0xE62E, 'ScaleGlyph': None,
		'Attributes': symAttrDefault},
		{'Enabled': True, 'Name': "Devicons",
		'Filename': "devicons.ttf",	'Exact': False, 'SymStart': 0xE600,
		'SymEnd': 0xE6C5, 'SrcStart': 0xE700, 'SrcEnd': 0xE7C5, 'ScaleGlyph': deviScaleList,
		'Attributes': symAttrDefault},
		{'Enabled': self.args.powerline, 'Name': "Powerline Symbols",
		'Filename': "PowerlineSymbols.otf", 'Exact': True, 'SymStart': 0xE0A0,
		'SymEnd': 0xE0A2, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': None,
		'Attributes': symAttrPowerline},
		{'Enabled': self.args.powerline, 'Name': "Powerline Symbols",
		'Filename': "PowerlineSymbols.otf", 'Exact': True, 'SymStart': 0xE0B0,
		'SymEnd': 0xE0B3, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': None,
		'Attributes': symAttrPowerline},
		{'Enabled': self.args.powerlineextra, 'Name': "Powerline Extra Symbols",
		'Filename': "PowerlineExtraSymbols.otf", 'Exact': True, 'SymStart': 0xE0A3,
		'SymEnd': 0xE0A3, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': None,
		'Attributes': symAttrPowerline},
		{'Enabled': self.args.powerlineextra, 'Name': "Powerline Extra Symbols",
		'Filename': "PowerlineExtraSymbols.otf", 'Exact': True, 'SymStart': 0xE0B4,
		'SymEnd': 0xE0C8, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': None,
		'Attributes': symAttrPowerline},
		{'Enabled': self.args.powerlineextra, 'Name': "Powerline Extra Symbols",
		'Filename': "PowerlineExtraSymbols.otf", 'Exact': True, 'SymStart': 0xE0CA,
		'SymEnd': 0xE0CA, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': None,
		'Attributes': symAttrPowerline},
		{'Enabled': self.args.powerlineextra, 'Name': "Powerline Extra Symbols",
		'Filename': "PowerlineExtraSymbols.otf", 'Exact': True, 'SymStart': 0xE0CC,
		'SymEnd': 0xE0D4, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': None,
		'Attributes': symAttrPowerline},
		{'Enabled': self.args.pomicons, 'Name': "Pomicons",
		'Filename': "Pomicons.otf", 'Exact': True, 'SymStart': 0xE000,
		'SymEnd': 0xE00A, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': None,
		'Attributes': symAttrDefault},
		{'Enabled': self.args.fontawesome, 'Name': "Font Awesome",
		'Filename': "FontAwesome.otf", 'Exact': True, 'SymStart': 0xF000,
		'SymEnd': 0xF2E0, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': fontAScaleList,
		'Attributes': symAttrFontA},
		{'Enabled': self.args.fontawesomeextension, 'Name': "Font Awesome Extension",
		'Filename': "font-awesome-extension.ttf", 'Exact': False, 'SymStart': 0xE000,
		'SymEnd': 0xE0A9, 'SrcStart': 0xE200, 'SrcEnd': 0xE2A9, 'ScaleGlyph': None,
		'Attributes': symAttrDefault}, # Maximize
		{'Enabled': self.args.powersymbols, 'Name': "Power Symbols",
		'Filename': "Unicode_IEC_symbol_font.otf", 'Exact': True, 'SymStart': 0x23FB,
		'SymEnd': 0x23FE, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': None,
		'Attributes': symAttrDefault}, # Power, Power On/Off, Power On, Sleep
		{'Enabled': self.args.powersymbols, 'Name': "Power Symbols",
		'Filename': "Unicode_IEC_symbol_font.otf", 'Exact': True, 'SymStart': 0x2B58,
		'SymEnd': 0x2B58, 'SrcStart': None, 'SrcEnd': None, 'ScaleGlyph': None,
		'Attributes': symAttrDefault}, # Heavy Circle (aka Power Off)
		{'Enabled': self.args.material, 'Name': "Material",
		'Filename': "materialdesignicons-webfont.ttf", 'Exact': False, 'SymStart': 0xF001,
		'SymEnd': 0xF847, 'SrcStart': 0xF500, 'SrcEnd': 0xFD46, 'ScaleGlyph': None,
		'Attributes': symAttrDefault},
		{'Enabled': self.args.weather, 'Name': "Weather Icons",
		'Filename': "weathericons-regular-webfont.ttf", 'Exact': False,
		'SymStart': 0xF000, 'SymEnd': 0xF0EB, 'SrcStart': 0xE300, 'SrcEnd': 0xE3EB, 'ScaleGlyph': None,
		'Attributes': symAttrDefault},
		{'Enabled': self.args.fontlinux, 'Name': "Font Logos (Font Linux)",
		'Filename': "font-logos.ttf", 'Exact': self.fontlinuxExactEncodingPosition,
		'SymStart': 0xF100, 'SymEnd': 0xF11C, 'SrcStart': 0xF300, 'SrcEnd': 0xF31C, 'ScaleGlyph': None,
		'Attributes': symAttrDefault},
		{'Enabled': self.args.octicons, 'Name': "Octicons",
		'Filename': "octicons.ttf", 'Exact': self.octiconsExactEncodingPosition,
		'SymStart': 0xF000, 'SymEnd': 0xF105, 'SrcStart': 0xF400, 'SrcEnd': 0xF505,
		'ScaleGlyph': octiScaleList, 'Attributes': symAttrDefault}, # Magnifying glass
		{'Enabled': self.args.octicons, 'Name': "Octicons",
		'Filename': "octicons.ttf", 'Exact': self.octiconsExactEncodingPosition,
		'SymStart': 0x2665, 'SymEnd': 0x2665, 'SrcStart': None, 'SrcEnd': None,
		'ScaleGlyph': octiScaleList, 'Attributes': symAttrDefault}, # Heart
		{'Enabled': self.args.octicons, 'Name': "Octicons",
		'Filename': "octicons.ttf", 'Exact': self.octiconsExactEncodingPosition,
		'SymStart': 0X26A1, 'SymEnd': 0X26A1, 'SrcStart': None, 'SrcEnd': None,
		'ScaleGlyph': octiScaleList, 'Attributes': symAttrDefault}, # Zap
		{'Enabled': self.args.octicons, 'Name': "Octicons",
		'Filename': "octicons.ttf", 'Exact': self.octiconsExactEncodingPosition,
		#'SymStart': 0xF27C, 'SymEnd': 0xF27C, 'SrcStart': 0xF4A9, 'SrcEnd': 0xF4A9,
		'SymStart': 0xF27C, 'SymEnd': 0xF2BD, 'SrcStart': 0xF4A9, 'SrcEnd': 0xF4EA,
		'ScaleGlyph': octiScaleList, 'Attributes': symAttrDefault}, # Desktop
		{'Enabled': self.args.custom, 'Name': "Custom",
		'Filename': self.args.custom, 'Exact': True,
		'SymStart': 0x0000, 'SymEnd': 0x0000, 'SrcStart': 0x0000, 'SrcEnd': 0x0000,
		'ScaleGlyph': None, 'Attributes': customAttr}]

		# yapf: enable

	def setupLineDimensions(self):
		"""
		win_ascent and win_descent are used to set the line height for windows fonts.
		hhead_ascent and hhead_descent are used to set the line height for mac fonts.

		Make the total line size even.  This seems to make the powerline separators
		center more evenly.
		"""
		if self.args.adjustLineHeight:
			if (self.sourceFont.os2_winascent +
			self.sourceFont.os2_windescent) % 2 != 0:
				self.sourceFont.os2_winascent += 1

			# Make the line size identical for windows and mac
			self.sourceFont.hhea_ascent = self.sourceFont.os2_winascent
			self.sourceFont.hhea_descent = -self.sourceFont.os2_windescent

		# Line gap add extra space on the bottom of the line which
		# doesn't allow the powerline glyphs to fill the entire line.
		self.sourceFont.hhea_linegap = 0
		self.sourceFont.os2_typolinegap = 0

	def getSourceFontDimensions(self):
		# Initial font dimensions
		self.fontDim = {
		'xmin': 0, 'ymin': -self.sourceFont.os2_windescent, 'xmax': 0,
		'ymax': self.sourceFont.os2_winascent, 'width': 0, 'height': 0, }

		# Find the biggest char width
		# Ignore the y-values, os2_winXXXXX values set above are used for line height
		#
		# 0x00-0x17f is the Latin Extended-A range
		for glyph in range(0x00, 0x17f):
			try:
				(_, _, xmax, _) = self.sourceFont[glyph].boundingBox()
			except TypeError:
				continue
			if self.fontDim['width'] < self.sourceFont[glyph].width:
				self.fontDim['width'] = self.sourceFont[glyph].width
			if xmax > self.fontDim['xmax']:
				self.fontDim['xmax'] = xmax

		# Calculate font height
		self.fontDim['height'] = abs(self.fontDim['ymin']) + self.fontDim['ymax']

	def getScaleFactor(self, symDim):
		scaleRatio = 1

		# We want to preserve x/y aspect ratio, so find biggest scale factor that allows symbol to fit
		scaleRatioX = self.fontDim['width'] / symDim['width']

		# fontDim['height'] represents total line height, keep our symbols sized based upon font's em
		# NOTE: is this comment correct? fontDim['height'] isn't used here
		scaleRatioY = self.sourceFont.em / symDim['height']
		if scaleRatioX > scaleRatioY:
			scaleRatio = scaleRatioY
		else:
			scaleRatio = scaleRatioX
		return scaleRatio

	def copyGlyphs(self, sourceFontStart, sourceFontEnd, symbolFont,
	symbolFontStart, symbolFontEnd, exactEncoding, scaleGlyph, setName,
	attributes):
		""" Copies symbol glyphs into self.sourceFont """
		progressText = ''
		careful = False
		glyphSetLength = 0

		if self.args.careful:
			careful = True

		if exactEncoding is False:
			sourceFontList = []
			sourceFontCounter = 0
			for i in range(sourceFontStart, sourceFontEnd + 1):
				sourceFontList.append(format(i, 'X'))

		scaleFactor = 0
		if scaleGlyph:
			symDim = getGlyphDimensions(symbolFont[scaleGlyph['ScaleGlyph']])
			scaleFactor = self.getScaleFactor(symDim)

		# Create glyphs from symbol font
		#
		# If we are going to copy all Glyphs, then assume we want to be careful
		# and only copy those that are not already contained in the source font
		if symbolFontStart == 0:
			symbolFont.selection.all()
			self.sourceFont.selection.all()
			careful = True
		else:
			symbolFont.selection.select((str("ranges"), str("unicode")),
			symbolFontStart, symbolFontEnd)
			self.sourceFont.selection.select((str("ranges"), str("unicode")),
			sourceFontStart, sourceFontEnd)

		# Get number of selected non-empty glyphs @TODO FIXME
		for index, symGlyph in enumerate(symbolFont.selection.byGlyphs):
			glyphSetLength += 1
		# end for

		if self.args.quiet is False:
			sys.stdout.write("Adding " + str(max(1, glyphSetLength)) + " Glyphs from " +
			setName + " Set \n")

		for index, symGlyph in enumerate(symbolFont.selection.byGlyphs):
			index = max(1, index)

			try:
				symAttr = attributes[symGlyph.unicode]
			except KeyError:
				symAttr = attributes['default']

			if exactEncoding:
				# use the exact same hex values for the source font as for the symbol font
				currentSourceFontGlyph = symGlyph.encoding

				# Save as a hex string without the '0x' prefix
				copiedToSlot = format(symGlyph.unicode, 'X')
			else:
				# use source font defined hex values based on passed in start and end
				# convince that this string really is a hex:
				currentSourceFontGlyph = int("0x" + sourceFontList[sourceFontCounter], 16)
				copiedToSlot = sourceFontList[sourceFontCounter]
				sourceFontCounter += 1

			if int(copiedToSlot, 16) < 0:
				print("Found invalid glyph slot number. Skipping.")
				continue

			if self.args.quiet is False:
				updateProgress(round(float(index + 1) / glyphSetLength, 2))

			# Prepare symbol glyph dimensions
			symDim = getGlyphDimensions(symGlyph)

			# check if a glyph already exists in this location
			if careful or 'careful' in symAttr['params']:
				if copiedToSlot.startswith("uni"):
					copiedToSlot = copiedToSlot[3:]
				codepoint = int("0x" + copiedToSlot, 16)
				if codepoint in self.sourceFont:
					if self.args.quiet is False:
						print("  Found existing Glyph at {}. Skipping...".format(copiedToSlot))

					# We don't want to touch anything so move to next Glyph
					continue

			# Select and copy symbol from its encoding point
			# We need to do this select after the careful check, this way we don't
			# reset our selection before starting the next loop
			symbolFont.selection.select(symGlyph.encoding)
			symbolFont.copy()

			# Paste it
			self.sourceFont.selection.select(currentSourceFontGlyph)
			self.sourceFont.paste()
			self.sourceFont[currentSourceFontGlyph].glyphname = symGlyph.glyphname
			scaleRatioX = 1
			scaleRatioY = 1

			# Now that we have copy/pasted the glyph, if we are creating a monospace
			# font we need to scale and move the glyphs.  It is possible to have
			# empty glyphs, so we need to skip those.
			if self.args.single and symDim['width'] and symDim['height']:
				# If we want to preserve that aspect ratio of the glyphs we need to
				# find the largest possible scaling factor that will allow the glyph
				# to fit in both the x and y directions
				if symAttr['stretch'] == 'pa':
					if scaleFactor and useScaleGlyph(symGlyph.unicode,
					scaleGlyph['GlyphsToScale']):
						# We want to preserve the relative size of each glyph to other glyphs
						# in the same symbol font.
						scaleRatioX = scaleFactor
						scaleRatioY = scaleFactor
					else:
						# In this case, each glyph is sized independently to each other
						scaleRatioX = self.getScaleFactor(symDim)
						scaleRatioY = scaleRatioX
				else:
					if 'x' in symAttr['stretch']:
						# Stretch the glyph horizontally to fit the entire available width
						scaleRatioX = self.fontDim['width'] / symDim['width']
			# end if single width

			# non-monospace (double width glyphs)
			# elif sym_dim['width'] and sym_dim['height']:
			# any special logic we want to apply for double-width variation
			# would go here

			if 'y' in symAttr['stretch']:
				# Stretch the glyph vertically to total line height (good for powerline separators)
				# Currently stretching vertically for both monospace and double-width
				scaleRatioY = self.fontDim['height'] / symDim['height']

			if scaleRatioX != 1 or scaleRatioY != 1:
				if 'overlap' in symAttr['params']:
					scaleRatioX *= 1 + symAttr['params']['overlap']
					scaleRatioY *= 1 + symAttr['params']['overlap']
				self.sourceFont.transform(psMat.scale(scaleRatioX, scaleRatioY))

			# Use the dimensions from the newly pasted and stretched glyph
			symDim = getGlyphDimensions(self.sourceFont[currentSourceFontGlyph])
			yAlignDistance = 0
			if symAttr['valign'] == 'c':
				# Center the symbol vertically by matching the center of the line height and center of symbol
				symYCenter = symDim['ymax'] - (symDim['height'] / 2)
				fontYCenter = self.fontDim['ymax'] - (self.fontDim['height'] / 2)
				yAlignDistance = fontYCenter - symYCenter

			# Handle glyph l/r/c alignment
			xAlignDistance = 0
			if symAttr['align']:
				# First find the baseline x-alignment (left alignment amount)
				xAlignDistance = self.fontDim['xmin'] - symDim['xmin']
				if symAttr['align'] == 'c':
					# Center align
					xAlignDistance += (self.fontDim['width'] / 2) - (symDim['width'] / 2)
				elif symAttr['align'] == 'r':
					# Right align
					xAlignDistance += self.fontDim['width'] - symDim['width']

			if 'overlap' in symAttr['params']:
				overlapWidth = self.fontDim['width'] * symAttr['params']['overlap']
				if symAttr['align'] == 'l':
					xAlignDistance -= overlapWidth
				if symAttr['align'] == 'r':
					xAlignDistance += overlapWidth

			alignMatrix = psMat.translate(xAlignDistance, yAlignDistance)
			self.sourceFont.transform(alignMatrix)

			# Ensure after horizontal adjustments and centering that the glyph
			# does not overlap the bearings (edges)
			self.removeGlyphNegBearings(self.sourceFont[currentSourceFontGlyph])

			# Needed for setting 'advance width' on each glyph so they do not overlap,
			# also ensures the font is considered monospaced on Windows by setting the
			# same width for all character glyphs. This needs to be done for all glyphs,
			# even the ones that are empty and didn't go through the scaling operations.
			# it should come after setting the glyph bearings
			self.setGlyphWidthMono(self.sourceFont[currentSourceFontGlyph])

			# reset selection so iteration works properly @TODO fix? rookie misunderstanding?
			# This is likely needed because the selection was changed when the glyph was copy/pasted
			if symbolFontStart == 0:
				symbolFont.selection.all()
			else:
				symbolFont.selection.select((str("ranges"), str("unicode")),
				symbolFontStart, symbolFontEnd)
		# end for

		if self.args.quiet is False or self.args.progressbars:
			sys.stdout.write("\n")

	def setSourceFontGlyphWidths(self):
		""" Makes self.sourceFont monospace compliant """

		for glyph in self.sourceFont.glyphs():
			if (glyph.width == self.fontDim['width']):
				# Don't tough the (negative) bearings if the width is ok
				# Ligartures will have these.
				continue

			if (glyph.width != 0):
				# If the width is zero this glyph is intened to be printed on top of another one.
				# In this case we need to keep the negative bearings to shift it 'left'.
				# Things like &Auml; have these: composed of U+0041 'A' and U+0308 'double dot above'
				#
				# If width is not zero, correct the bearings such that they are within the width:
				self.removeGlyphNegBearings(glyph)

			self.setGlyphWidthMono(glyph)

	def removeGlyphNegBearings(self, glyph):
		""" Sets passed glyph's bearings 0.0 if they are negative. """
		try:
			if glyph.left_side_bearing < 0.0:
				glyph.left_side_bearing = 0.0
			if glyph.right_side_bearing < 0.0:
				glyph.right_side_bearing = 0.0
		except:
			pass

	def setGlyphWidthMono(self, glyph):
		""" Sets passed glyph.width to self.fontDim.width.

		self.fontDim.width is set with self.get_sourcefontDimensions().
		"""
		try:
			glyph.width = self.fontDim['width']
		except:
			pass


def replaceFontName(fontName, replacementDict):
	""" Replaces all keys with vals from replacement_dict in font_name. """
	for key, val in replacementDict.items():
		fontName = fontName.replace(key, val)
	return fontName


def makeSurePathExists(path):
	""" Verifies path passed to it exists. """
	try:
		makedirs(path)
	except OSError as exception:
		if exception.errno != errno.EEXIST:
			raise


def getGlyphDimensions(glyph):
	""" Returns dict of the dimesions of the glyph passed to it. """
	bbox = glyph.boundingBox()
	return {
	'xmin': bbox[0], 'ymin': bbox[1], 'xmax': bbox[2], 'ymax': bbox[3],
	'width': bbox[2] + (-bbox[0]), 'height': bbox[3] + (-bbox[1]), }


def useScaleGlyph(unicodeValue, glyphList):
	""" Determines whether or not to use scaled glyphs for glyphs in passed glyph_list """
	for i in glyphList:
		if isinstance(i, tuple):
			if i[0] <= unicodeValue <= i[1]:
				return True
		else:
			if unicodeValue == i:
				return True
	return False


def updateProgress(progress):
	""" Updates progress bar length.

	Accepts a float between 0.0 and 1.0. Any int will be converted to a float.
	A value at 1 or bigger represents 100%
	modified from: https://stackoverflow.com/questions/3160699/python-progress-bar
	"""
	barLength = 40 # Modify this to change the length of the progress bar
	if isinstance(progress, int):
		progress = float(progress)
	if progress >= 1:
		progress = 1
	block = int(round(barLength * progress))
	text = "\r╢{0}╟ {1}%".format("█"*block + "░" * (barLength-block),
	int(progress * 100))
	sys.stdout.write(text)
	sys.stdout.flush()


def checkFontForgeMinVersion():
	""" Verifies installed FontForge version meets minimum requirement. """
	minimumVersion = 20141231
	actualVersion = int(fontforge.version())

	# un-comment following line for testing invalid version error handling
	# actualVersion = 20120731

	# versions tested: 20150612, 20150824
	if actualVersion < minimumVersion:
		sys.stderr.write(
		"{}: You seem to be using an unsupported (old) version of fontforge: {}\n"
		.format(PROJECT_NAME, actualVersion))
		sys.stderr.write("{}: Please use at least version: {}\n"
		.format(PROJECT_NAME, minimumVersion))
		sys.exit(1)


def setupArgumentsAndRun():
	""" set up the arguments """
	symFontArgs = []
	parser = ArgumentParser(
	description=(
	'Nerd Fonts Font Patcher: patches a given font with programming and development related glyphs\n\n'
	'* Website: https://www.nerdfonts.com\n'
	'* Version: ' + VERSION + '\n'
	'* Development Website: https://github.com/ryanoasis/nerd-fonts\n'
	'* Changelog: https://github.com/ryanoasis/nerd-fonts/blob/master/changelog.md'
	), formatter_class=RawTextHelpFormatter)

	# yapf: disable
	parser.add_argument('font', help='The path to the font to patch or the path '
	'to the directory (e.g., Inconsolata.otf)')
	parser.add_argument('-v', '--version', action='version', version=PROJECT_NAME +
	": %(prog)s (" + VERSION + ")")
	parser.add_argument('-s', '--mono', '--use-single-width-glyphs',
	dest='single', default=False, action='store_true', help='Whether to '
	'generate the glyphs as single-width not double-width (default is double-width)')
	parser.add_argument('-l', '--adjust-line-height', dest='adjustLineHeight',
	default=False, action='store_true', help='Whether to adjust line heights '
	'(attempt to center powerline separators more evenly)')
	parser.add_argument('-q', '--quiet', '--shutup', dest='quiet', default=False,
	action='store_true', help='Do not generate verbose output')
	parser.add_argument('-w', '--windows', dest='windows', default=False,
	action='store_true', help='Limit the internal font name to 31 characters '
	'(for Windows compatibility)')
	parser.add_argument('-c', '--complete', dest='complete', default=False,
	action='store_true', help='Add all available Glyphs')
	parser.add_argument('--compat', dest='compat', default=False,
	action='store_true', help='Force compatibility with nerd font complete sets')
	parser.add_argument('--careful', dest='careful', default=False,
	action='store_true', help='Do not overwrite existing glyphs if detected')
	parser.add_argument('--removeligs', '--removeligatures',
	dest='removeligatures', default=False,	action='store_true',
	help='Removes ligatures specificed in JSON configuration file')
	parser.add_argument('--postprocess', dest='postprocess', default=False,
	type=str, nargs='?', help='Specify a Script for Post Processing')
	parser.add_argument('--configfile', dest='configfile', default=False,
	type=str, nargs='?', help='Specify a file path for JSON configuration file '
	'(see sample: src/config.sample.json)')
	parser.add_argument('--custom', dest='custom', default=False, type=str,
	nargs='?', help='Specify a custom symbol font. All new glyphs will be '
	'copied, with no scaling applied.')
	parser.add_argument('-ext', '--extension', dest='extension', default="",
	type=str, nargs='?', help='Change font file type to create (e.g., ttf, otf)')
	parser.add_argument('-out', '--outputdir', dest='outputdir', default=".",
	type=str, nargs='?', help='The directory to output the patched font file to')

	# symbol fonts to include arguments
	symFontGroup = parser.add_argument_group('Symbol Fonts')
	symFontGroup.add_argument('--fontawesome', dest='fontawesome',
	default=False, action='store_true',	help='Add Font Awesome Glyphs '
	'(http://fontawesome.io/)')
	symFontGroup.add_argument('--fontawesomeextension',
	dest='fontawesomeextension', default=False, action='store_true',
	help='Add Font Awesome Extension Glyphs (https://andrelzgava.github.io/'
	'font-awesome-extension/)')
	symFontGroup.add_argument('--fontlinux', '--fontlogos', dest='fontlinux',
	default=False, action='store_true', help='Add Font Linux and other open '
	'source Glyphs (https://github.com/Lukas-W/font-logos)')
	symFontGroup.add_argument('--octicons', dest='octicons', default=False,
	action='store_true', help='Add Octicons Glyphs (https://octicons.github.com)')
	symFontGroup.add_argument('--powersymbols', dest='powersymbols',
	default=False, action='store_true', help='Add IEC Power Symbols '
	'(https://unicodepowersymbol.com/)')
	symFontGroup.add_argument('--pomicons', dest='pomicons', default=False,
	action='store_true', help='Add Pomicon Glyphs (https://github.com/gabrielelana/pomicons)')
	symFontGroup.add_argument('--powerline', dest='powerline', default=False,
	action='store_true', help='Add Powerline Glyphs')
	symFontGroup.add_argument('--powerlineextra', dest='powerlineextra',
	default=False, action='store_true',	help='Add Powerline Glyphs '
	'(https://github.com/ryanoasis/powerline-extra-symbols)')
	symFontGroup.add_argument('--material', '--materialdesignicons', '--mdi',
	dest='material', default=False, action='store_true',
	help='Add Material Design Icons (https://github.com/templarian/MaterialDesign)')
	symFontGroup.add_argument('--weather', '--weathericons', dest='weather',
	default=False, action='store_true', help='Add Weather Icons '
	'(https://github.com/erikflowers/weather-icons)')

	# yapf: enable


	args = parser.parse_args()

	# if you add a new font, set it to True here inside the if condition
	if args.complete:
		args.fontawesome = True
		args.fontawesomeextension = True
		args.fontlinux = True
		args.octicons = True
		args.powersymbols = True
		args.pomicons = True
		args.powerline = True
		args.powerlineextra = True
		args.material = True
		args.weather = True

	if not args.complete:
		# add the list of arguments for each symbol font to the list sym_font_args
		for action in symFontGroup._group_actions:
			symFontArgs.append(action.__dict__['option_strings'])

		# determine whether or not all symbol fonts are to be used
		fontComplete = True
		for symFontArgAliases in symFontArgs:
			found = False
			for alias in symFontArgAliases:
				if alias in sys.argv:
					found = True
			if found is not True:
				fontComplete = False
		args.complete = fontComplete

	# for each font:
	if isdir(args.font):
		files = [
		join(args.font, file) for file in listdir(args.font)
		if isfile(join(args.font, file))]
		for file in files:
			args.font = file
			patcher = FontPatcher(args, symFontArgs)
			patcher.patch()
	else:
		patcher = FontPatcher(args, symFontArgs)
		patcher.patch()


def main():
	""" entry point """
	checkFontForgeMinVersion()
	setupArgumentsAndRun()


if __name__ == "__main__":
	__dir__ = dirname(abspath(__file__))
	main()
