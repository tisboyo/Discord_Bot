# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

# Disables snake_case warning in pylint
# pylint: disable=invalid-name

import logging
import string

import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions

logger = logging.getLogger(__name__)


class Resistor(commands.Cog):
    """
    Resistor Class to use resistor command for figuring out
    the value of a resistor.
    """

    def __init__(self, client):
        self.client = client

    @commands.command()
    @Permissions.check(role="everyone")
    async def resistor(self, ctx, *, message="help"):
        """
        resistor Replies with the value of a resistor

        Returns the value of a resistor when passed the appropriate color
        codes or numeric value for surface mount.
        """
        # Always required to pass self when inside of a class for every command
        # Doing *, message in the variables puts everything after resistor into
        # the message variable

        # Setup a couple functions to make life easier.
        def resistorColor(color, num, dictionary):
            """
            resistorColor(color as String, num as String, dictionary as
            Dictionary, invalidResult as Boolean)

            returns num as String, invalidResult as Boolean

            Used to determine the numerical value of a color for both the
            Significant and Multiplier
            """

            if color in dictionary:  # The color recieved was in the dictionary
                return num + dictionary.get(color), False

            # color was not found, so return invalidResult as True
            return "", True

        def humanReadable(num):
            """
            humanReadble(num as Integer)

            returns finalValue as String

            Takes a value and returns a human readble, 1K, 1M, 1G, etc to output
            to the user.
            """
            # Check the value of the resistor and reduce it to a human readable number.
            if num >= 1000000000:  # Giga Ohm
                finalValue = num / 1000000000
                finalValue = f"{finalValue}G"

            elif num >= 1000000:  # Mega Ohm
                finalValue = num / 1000000
                finalValue = f"{finalValue}M"

            elif num >= 1000:  # Kilo Ohm
                finalValue = num / 1000
                finalValue = f"{finalValue}k"

            else:
                finalValue = num
                finalValue = f"{finalValue}"

            return finalValue

        # Setup some variables
        invalidResult = False
        smdResistor = False  # Used to track if we are doing a surface mount or not
        num = ""

        # Get our query from the discord message and split it.
        userInput = message
        colors = userInput.split()

        # How many colors do we have in the userInput
        howManyColors = len(colors)

        if howManyColors == 1 and colors[0] == "help":
            invalidResult = True  # Not really invalid, but forces the help
        elif howManyColors == 1 and (len(colors[0]) == 3 or len(colors[0]) == 4):
            smdResistor = True
        elif howManyColors == 4:
            # if it's a 4 band resistor, colorsChecked = 0
            colorsChecked = 0
        elif howManyColors == 5:
            # if it's a 5 band resistor, colorsChecked = -1
            colorsChecked = -1

            # This sets the pointer for how many times to run thru the function resistorColor

        elif howManyColors > 5:
            invalidResult = True
        else:
            invalidResult = True

        if not smdResistor and not invalidResult:
            # Checking a through hole resistor by color code

            # Loop through the colors that were given
            for color in colors:

                if invalidResult:
                    # Just quit now, we know we don't have a good input.
                    break

                # Increaes our counter so we know which color we are on for what.
                colorsChecked += 1

                # Check to make sure we got at least 4 or 5 values passed, otherwise invalidResult
                if howManyColors in (4, 5):

                    # Check the first 2 or 3 bands depending on howManyColors
                    if colorsChecked <= 2:

                        # Define the dictionary for the significant colors
                        dictionary = {
                            "black": "0",
                            "brown": "1",
                            "red": "2",
                            "orange": "3",
                            "yellow": "4",
                            "green": "5",
                            "blue": "6",
                            "violet": "7",
                            "purple": "7",
                            "grey": "8",
                            "gray": "8",
                            "white": "9",
                        }

                        num, invalidResult = resistorColor(color, num, dictionary)

                    elif colorsChecked == 3:  # Check the multiplier color

                        # Define the dictionary of multiplier colors
                        dictionary = {
                            "black": "",
                            "brown": "0",
                            "red": "00",
                            "orange": "000",
                            "yellow": "0000",
                            "green": "00000",
                            "blue": "000000",
                            "purple": "0000000",
                            "violet": "0000000",
                            "grey": "00000000",
                            "gray": "00000000",
                            "white": "000000000",
                        }

                        num, invalidResult = resistorColor(color, num, dictionary)

                    elif colorsChecked == 4:  # Check the tolerance color

                        dictionary = {
                            "brown": "1%",
                            "red": "2%",
                            "green": ".5%",
                            "blue": ".25%",
                            "purple": ".1%",
                            "violet": ".1%",
                            "grey": ".05%",
                            "gray": ".05%",
                            "gold": "5%",
                            "silver": "10%",
                            "none": "20%",
                        }

                        # We are not going to actually pass num because we don't want to affect
                        # the number stored, but want to create the tolerance string.
                        tolerance, invalidResult = resistorColor(color, "", dictionary)

                        tolerance = f"with ±{tolerance} tolerance"

                else:
                    invalidResult = True

            # End of color check loop

            # Check to make sure we didn't have any invalid inputs
            if not invalidResult:

                # Convert our num string from earlier to something we can do math with.
                num = int(num)

                finalValue = humanReadable(num)

                output = f"Resistor value is {finalValue} Ω {tolerance}"
                await ctx.send(output)

        elif smdResistor and not invalidResult:  # We are checking a smd resistor

            # http://www.resistorguide.com/resistor-smd-code/#The_EIA-96_System

            smdCode = list(colors[0])

            if len(smdCode) == 3:

                if smdCode[2] not in string.ascii_letters:
                    # The third character is NOT a letter, using the older system

                    # Good test cases
                    # https://www.hobby-hour.com/electronics/3-digit-smd-resistors.php

                    lessThanOneHundred = False

                    # Check if any of the codes are an R indicating a decimal
                    # indicating a value less than 100
                    for x in range(2):
                        if smdCode[x] == "R":
                            smdCode[x] = "."
                            lessThanOneHundred = True
                            break

                    tempString = smdCode[0] + smdCode[1]

                    if lessThanOneHundred:
                        tempString = tempString + smdCode[2]
                        num = float(tempString)
                    else:
                        # First, Second and Third numbers are value * 10 to the power of
                        # the Fourth number.

                        num = float(tempString) * (10 ** int(smdCode[2]))

                    finalValue = humanReadable(num)

                    output = f"Resistor value is {finalValue} Ω"
                    await ctx.send(output)

                else:
                    # Third character IS a letter, 3 digits, with 3rd being a
                    # letter is EIA96 system.
                    # This system uses a straight table lookup, instead of a formula.
                    codeDictionary = {
                        "01": 100,
                        "02": 102,
                        "03": 105,
                        "04": 107,
                        "05": 110,
                        "06": 113,
                        "07": 115,
                        "08": 118,
                        "09": 121,
                        "10": 124,
                        "11": 127,
                        "12": 130,
                        "13": 133,
                        "14": 137,
                        "15": 140,
                        "16": 143,
                        "17": 147,
                        "18": 150,
                        "19": 154,
                        "20": 158,
                        "21": 162,
                        "22": 165,
                        "23": 169,
                        "24": 174,
                        "25": 178,
                        "26": 182,
                        "27": 187,
                        "28": 191,
                        "29": 196,
                        "30": 200,
                        "31": 205,
                        "32": 210,
                        "33": 215,
                        "34": 221,
                        "35": 226,
                        "36": 232,
                        "37": 237,
                        "38": 243,
                        "39": 249,
                        "40": 255,
                        "41": 261,
                        "42": 267,
                        "43": 274,
                        "44": 280,
                        "45": 287,
                        "46": 294,
                        "47": 301,
                        "48": 309,
                        "49": 316,
                        "50": 324,
                        "51": 332,
                        "52": 340,
                        "53": 348,
                        "54": 357,
                        "55": 365,
                        "56": 374,
                        "57": 383,
                        "58": 392,
                        "59": 402,
                        "60": 412,
                        "61": 422,
                        "62": 432,
                        "63": 442,
                        "64": 453,
                        "65": 464,
                        "66": 475,
                        "67": 487,
                        "68": 499,
                        "69": 511,
                        "70": 523,
                        "71": 536,
                        "72": 549,
                        "73": 562,
                        "74": 576,
                        "75": 590,
                        "76": 604,
                        "77": 619,
                        "78": 634,
                        "79": 649,
                        "80": 665,
                        "81": 681,
                        "82": 698,
                        "83": 715,
                        "84": 732,
                        "85": 750,
                        "86": 768,
                        "87": 787,
                        "88": 806,
                        "89": 825,
                        "90": 845,
                        "91": 866,
                        "92": 887,
                        "93": 909,
                        "94": 931,
                        "95": 953,
                        "96": 976,
                    }

                    multiplierDictionary = {
                        "Z": 0.001,
                        "Y": 0.01,
                        "R": 0.01,
                        "X": 0.1,
                        "S": 0.1,
                        "A": 1,
                        "B": 10,
                        "H": 10,
                        "C": 100,
                        "D": 1000,
                        "E": 10000,
                        "F": 100000,
                    }

                    code = smdCode[0] + smdCode[1]  # Recombine just the first 2 numbers
                    multiplier = smdCode[2]

                    if code in codeDictionary and multiplier in multiplierDictionary:

                        num = codeDictionary[code] * multiplierDictionary[multiplier]

                        finalValue = humanReadable(num)

                        output = f"Resistor value is {finalValue} Ω"

                        await ctx.send(output)

                    else:
                        invalidResult = True
            elif len(smdCode) == 4:
                # Good test cases
                # https://www.hobby-hour.com/electronics/4-digit-smd-resistors.php

                lessThanOneHundred = False

                # Check if any of the codes are an R indicating a decimal
                # indicating a value less than 100
                for x in range(3):
                    if smdCode[x] == "R":
                        smdCode[x] = "."
                        lessThanOneHundred = True
                        break

                tempString = smdCode[0] + smdCode[1] + smdCode[2]

                if lessThanOneHundred:
                    tempString = tempString + smdCode[3]
                    num = float(tempString)
                else:
                    # First, Second and Third numbers are value * 10 to the power of
                    # the Fourth number.

                    num = float(tempString) * (10 ** int(smdCode[3]))

                finalValue = humanReadable(num)

                output = f"Resistor value is {finalValue} Ω"
                await ctx.send(output)

        if invalidResult:  # Uh oh, the user didn't give us valid input.

            # Embed a help guide
            embed = discord.Embed(title="Resistor Calculator", description="Values that I can understand")
            embed.set_thumbnail(url="http://educ8s.tv/wp-content/uploads/2014" "/11/Resistor-Icon-147x118.png")

            embed.add_field(
                name="Significant figures",
                value="black, brown, red," "orange, yellow, green, blue, violet, grey, white",
                inline=True,
            )

            embed.add_field(
                name="Multiplier",
                value="black, brown, red, orange, " "yellow, green, blue, violet, grey, white",
                inline=True,
            )

            embed.add_field(
                name="Tolerance",
                value="brown, red, green, blue, violet," "grey, gold, silver, none",
                inline=True,
            )

            embed.add_field(
                name="Surface Mount",
                value="You can also use a 3 or " "4 digit surface mount code",
            )

            embed.set_footer(
                text="Use .resistor followed by appropriate colors. "
                "For a 3 band resistor, use 'none' as the 4th (tolerance) "
                " band. I can currently do 3, 4 and 5 band resistors, "
                "and 3 and 4 number surface mount resistors."
            )

            await ctx.send(content=None, embed=embed)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    Resistor class setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Resistor(client))
    logger.info(f"Loaded {__name__}")
