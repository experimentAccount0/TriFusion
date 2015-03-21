#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  
#  Copyright 2012 Unknown <diogo@arch>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  Author: Diogo N. Silva
#  Version: 0.1
#  Last update: 11/02/14

import re
from collections import OrderedDict


class PartitionException(Exception):
    pass


class InvalidPartitionFile(Exception):
    pass


class Partitions():
    """
    The Partitions class is used to define partitions for Alignment objects and
    associate substitution models for each partition. Partitions may be set
    in two ways:

    ..: Partition files: Being Nexus charset blocks and RAxML partition files
    currently supported
    ..: Tuple-like objects: Containing the ranges and names of the partitions

    A SubstitutionModels object will be associated to each partition, and by
    default there will be no substitution model selected.
    """

    _models = {"mrbayes": {}}

    #===========================================================================
    #   MrBayes models
    #===========================================================================
    """
    MrBayes substitution models are stored in the dictionary _models["mrbayes"].
    The keys of the dictionary are the name of the substitution models (usually
    in capital letters) and the values will contain the instructions to
    specific such model in a list. Each element of the list corresponds to one
    line
    """

    # GTR
    _models["GTR"] = ["nst=6"]

    # SYM
    _models["SYM"] = ["nst=6", "statefreqpr=fixed(equal)"]

    # HKY
    _models["HKY"] = ["nst=2"]

    # K2P
    _models["K2P"] = ["nst=2", "statefreqpr=fixed(equal)"]

    # F81
    _models["F81"] = ["nst=1"]

    # JC
    _models["JC"] = ["nst=1", "statefreqpr=fixed(equal)"]

    def __init__(self):
        """
        Setting the self._partitions private attribute. This will contain an
        ordered dictionary with the partition names as keys and information on
        their range and substitution model object as values. The ranges will be
        in tuple format with the initial position as the first element and
        final position as the second element

        e.g. self.partitions["GeneA"] = [(0, 953), SubstitutionModels]
        Defines the partition GeneA whose sequence spans from 0 to the 953rd
        character
        """

        """
        The length of the locus may be necessary when partitions are defined
        in the input files using the "." notation, meaning the entire locus.
        Therefore, to convert this notation into workable integers, the size
        of the locus must be provided using the set_length method.
        """
        self.partition_length = 0

        """
        partitions will contain the name and range of the partitions for a given
        alignment object. Both gene and codon partitions will be stored in this
        attribute, but gene partitions are the main entries. An example of
        different stored partitions is:

        partitions = {"partitionA": ((0, 856,) False),
                      "partitionB": ((857, 1450), [857,858,859] }

        "partitionA" is a simple gene partition ranging from 0 to 856, while
        "partitionB" is an assembly of codon partitions. The third element of
        the tuple is destined to codon partitions. If there are none, it should
        be False. If there are codon partitions, a list should be provided with
        the desired initial codons. In the example above, "partitionB" has
        actually 3 partitions starting at the first, second and third sequence
        nucleotide of the main partition.
        """
        self.partitions = OrderedDict()

        """
        partitions_index will remember the index of all added partitions. This
        attribute was created because codon models are added to the same parent
        partitions, thus losing their actual index. This is important for
        Nexus files, where models are applied to the index of the partition.
        This will simply store the partition names, which can be accessed using
        their index, or searched to return their index. To better support codon
        partitions, each entry in the partitions_index will consist in a list,
        in which the first element is the partition name, and the second element
        is the index of the subpartition. An example would be:

        self.partitions_index = [["partA", 0], ["partA", 1], ["partA", 2],
                                 ["partB", 0]]

        in which, partA has 3 codon partitions, and partB has only one partition

        """
        self.partitions_index = []

        """
        The partitions_alignments attribute will associate the partition with
        the corresponding alignment files. For single alignment partitions,
        this will provide information on the file name. For multiple alignments,
        besides the information of the file names, it will associate which
        alignments are contained in a given partition.
        An example would be:

        self.partitions_alignments = {"PartitionA": ["FileA.fas"], "PartitionB":
            ["FileB.fas", "FileC.fas"]}

        """

        self.partitions_alignments = {}

        """
        The private self.models attribute will contain the same key list as
        self._partitions and will associate the substitution models to each
        partitions. For each partition, the format should be as follows:

        self.models["partA"] = [[[..model_params..]],[..model_names..]]

        The first element is a list that may contain the substitution model
        parameters for up to three subpartitions, and the second element is also
        a list with the corresponding names of the substitution models
        """

        self.models = OrderedDict()

        """
        The counter attribute will be used as an indication of where the last
        partition ends when one or more partitions are added
        """
        self.counter = 0

    def __iter__(self):
        """
        The class iterator will iterate over a list containing the partition
        names and a modified version of their ranges that is compatible with
        other software (unlike the 0 offset of python)
        :return:
        """

        return iter(self.partitions.items())

    def set_length(self, length):
        """
        Sets the length of the locus. This may be important to convert certain
        partition defining nomenclature, such as using the "." to indicate
        whole length of the alignment
        :param length: int. Length of the alignments
        """

        self.partition_length = length

    #===========================================================================
    # Parsers
    #===========================================================================

    @staticmethod
    def _get_file_format(partition_file):
        """ Tries to guess the format of the partition file (Whether it is
         Nexus of RAxML's) """
        file_handle = open(partition_file)

        # Skips first empty lines, if any
        header = file_handle.readline()
        while header.startswith("\n"):
            header = next(file_handle)

        fields = header.split()
        if fields[0].lower() == "charset":
            partition_format = "nexus"
        else:
            partition_format = "raxml"

        return partition_format

    def read_from_file(self, partitions_file):
        """
        This function parses a file containing partitions. Supports
        partitions files similar to RAxML's and NEXUS charset blocks. The
        NEXUS file, however, must only contain the charset block. The
        model_nexus argument provides a namespace for the model variable in
        the nexus format, since this information is not present in the file.
        However, it assures consistency on the Partition object
        :param partitions_file: string, file name of the file containing the
        partitions
        """

        # Get the format of the partition file
        partition_format = self._get_file_format(partitions_file)

        part_file = open(partitions_file)

        # TODO: Add suport for codon partitions in raxml format
        if partition_format == "raxml":
            for line in part_file:
                # A wrongly formated raxml partition file may be provided, in
                # which case an IndexError exception will be raised. This will
                # handle that exception
                try:
                    fields = line.split(",")
                    # Get model name as string
                    model_name = fields[0]
                    # Get partition name as string
                    partition_name = fields[1].split("=")[0].strip()
                    # Get partition range as list of int
                    partition_range_temp = fields[1].split("=")[1]
                    partition_range = [int(x) - 1 for x in
                                       partition_range_temp.strip().split("-")]
                    # Add information to partitions storage
                    self.add_partition(partition_name,
                                       locus_range=partition_range,
                                       model=model_name)
                except IndexError:
                    return InvalidPartitionFile("Badly formatted partitions "
                                                "file")

        elif partition_format == "nexus":
            for line in part_file:
                self.read_from_nexus_string(line)

    def read_from_nexus_string(self, string, file_name=None):
        """
        Parses the partition defined in a charset command
        :param string: string with the charset command.
        :param file_name: string. Name of the current file name
        """

        fields = string.split("=")
        partition_name = fields[0].split()[1].strip()

        # If this list has 2 elements, it should be a simple gene partition
        # If it has 3 elements, it should be a codon partition
        partition_full = re.split(r"[-\\]", fields[1].strip().replace(";", ""))

        # If partition is defined using "." notation to mean full length
        if partition_full[1] == ".":
            if self.partition_length:
                partition_range = [int(partition_full[0]) - 1,
                                   self.partition_length - 1]
            else:
                raise PartitionException("The length of the locus must be "
                                         "provided when partitions are defined"
                                         " using '.' notation to mean full"
                                         " length")
        else:
            partition_range = [int(partition_full[0]) - 1,
                               int(partition_full[1]) - 1]

        self.add_partition(partition_name, locus_range=partition_range,
                           file_name=file_name)

    def get_partition_names(self):
        """
        :return: list containing the names of the partitions. When a parent
        partition has multiple codon partitions, it returns a partition name
        for every codon starting position present in the second element
        of the value
        """

        names = []

        for part, vals in self.partitions.items():
            if vals[1]:
                names.extend([part + "_%s" % (x + 1) for x in vals[1]])
            else:
                names.append(part)

        return names

    def read_from_dict(self, dict_obj):
        """
        Parses partitions defined and stored in a special OrderedDict. The
        values of dict_obj should be the partition names and their corresponding
        values should contain the loci range and substitution model, if any

        Example

        dict_obj = OrderedDict(("GeneA", [(0,234), "GTR"]), ("GeneB", [(235,
                                865), "JC"))
        :param dict_obj: And OrderedDict object
        """

        for k, v in dict_obj:
            # Determining if value contains only the range or the substitution
            # model as well
            if len(v) > 1:
                self.add_partition(k, locus_range=v[0], model=v[1])
            else:
                self.add_partition(k, locus_range=v[0])

    def is_single(self):
        """
        :return: Boolean. Returns True is there is only a single partition
        defined, and False if there are multiple partitions
        """

        if len(self.partitions) == 1:
            if not [x for x in self.partitions.values()][0][1]:
                return True
            else:
                return False
        else:
            return False

    def _find_parent(self, max_range):
        """
        Internal method that finds a parent partition of a codon partition
        :param max_range: The maximum range of the codon partition
        :return: The name of the parent partition, from self.partitions
        """

        for part, vals in self.partitions.items():
            lrange = vals[0]
            if lrange[1] == max_range:
                return part

    def add_partition(self, name, length=None, locus_range=None, codon=False,
                      use_counter=False, model=None, file_name=None):
        """
        Adds a new partition providing the length or the range of current
        alignment. If both are provided, the length takes precedence.The range
        of the partition should be in python index, that is, the first position
        should be 0 and not 1.
        :param name: string. Name of the alignment
        :param length: int. Length of the alignment
        :param locus_range: list/tuple. Range of the partition
        :param codon: If the codon partitions are already defined, provide the
        starting points in list format, e.g: [1,2,3]
        :param model: string. [optional] Name of the substitution model
        :param file_name: string. If the file name is not provided by the name
        argument (which is instead the name of a partition), use this argument.

        IMPORTANT NOTE on self.model: The self.model attribute was designed
        in a way that allows the storage of different substitution models
        inside the same partition name. This is useful for codon partitions that
        share the same parent partition name. So, for example, a parent
        partition named "PartA" with 3 codon partitions can have a different
        model for each one like this:

        self.models["PartA"] = [[[..model1_params..], [..model2_params..],
            [..model3_params..]], [GTR, GTR, GTR]]

        """

        if name in self.partitions:
            raise PartitionException("Partition name %s is already in partition"
                                     "table" % name)

        # When length is provided
        if length:
            # Add partition to index list
            self.partitions_index.append([name, 0])
            # Add partition to alignment list
            self.partitions_alignments[file_name if file_name else name] = \
                [name]
            # Create empty model attribute for a single partition
            self.models[name] = [[[]], [None]]

            self.partitions[name] = [(self.counter,
                                      self.counter + (length - 1)), codon]
            self.counter += length

        # When a list/tuple range is provided
        elif locus_range:

            # If the maximum range of the current partition is already included
            # in some other partition, and no codon partitions were provided
            # using the "codon" argument, then it should be an undefined codon
            # partition and should be added to an existing partition
            if locus_range[1] <= self.counter and not codon:

                # Find the parent partition
                parent_partition = self._find_parent(locus_range[1])

                # If no codon partition is present in the parent partition,
                # create one
                if not self.partitions[parent_partition][1]:
                    # Add partition to index list
                    self.partitions_index.append([parent_partition, 1])
                    # Create empty model attribute for two partitions
                    self.models[parent_partition] = [[[], []], [None, None]]

                    parent_start = self.partitions[parent_partition][0][0]
                    self.partitions[parent_partition][1] = [parent_start,
                                                            locus_range[0]]
                else:
                    # Create empty model attribute for additional partitions
                    self.models[parent_partition][0].append([])
                    self.models[parent_partition][1].append(None)

                    # Add partition to index list
                    self.partitions_index.append([parent_partition, 2])

                    self.partitions[parent_partition][1].append(locus_range[0])

            # Else, create the new partition
            else:
                # Create empty model attribute for a single partition
                self.models[name] = [[[]], [None]]
                 # Add partition to index list
                self.partitions_index.append([name, 0])
                self.partitions_alignments[file_name if file_name else name] =\
                    [name]
                if use_counter:
                    self.partitions[name] = [(self.counter + locus_range[0],
                                             self.counter + locus_range[1]),
                                             [self.counter + x for x in codon]]
                else:
                    self.partitions[name] = [(locus_range[0], locus_range[1]),
                                             codon]

                self.counter = locus_range[1] + 1

    #===========================================================================
    # Model handling
    #===========================================================================

    def parse_nexus_model(self, string):
        """
        Parses a substitution model defined in a prset and/or lset command
        :param string: string with the prset or lset command
        """

        string = string.lower()

        # Find out which partitions the current parameters apply to. If
        # detected, it should be something like "applyto=(1,2)"
        applyto = re.findall(r"applyto=\(.*\)", string)
        # Find parameters
        nst = re.findall(r"nst=[0-9]", string)
        statefreqpr = re.findall(r"statefreqpr=.*\)", string)

        # Collect params
        params = [x[0] for x in [nst, statefreqpr] if x]

        if applyto:
            if applyto == ["applyto=(all)"]:
                for partition in self.partitions:
                    self.models[partition][0] += params
            else:
                # Get target partitions
                part_index = [int(x) for x in
                              re.split("[()]", applyto[0])[1].split(",")]
                for i in part_index:
                    part = self.partitions_index[i - 1]
                    # Get partition name
                    part_name = part[0]
                    # Get subpartition index. 0 if single partition, other if
                    # multiple subpartition
                    part_subpart = part[1]
                    self.models[part_name][0][part_subpart] += params

    # def set_model_name(self):
    #     """
    #     This method should be used once all partitions have been defined. It
    #     takes the substitution model parameters of each partition and
    #     :return:
    #     """


    # def write_to_file(self, output_format, output_file, model="LG"):
    #     """ Writes the Partitions object into an output file according to the
    #      output_format. The supported output formats are RAxML and Nexus.
    #      9The model option is for the RAxML format """
    #
    #     if output_format == "raxml":
    #         outfile_handle = open(output_file + ".part.File", "w")
    #         for part in self.partitions:
    #             partition_name = part[0]
    #             partition_range = "-".join([x for x in part[1]])
    #             outfile_handle.write("%s, %s = %s\n" % (model,
    #                                                     partition_name,
    #                                                     partition_range))
    #
    #         outfile_handle.close()
    #
    #     elif output_format == "nexus":
    #         outfile_handle = open(output_file + ".charset", "w")
    #         for part in self.partitions:
    #             outfile_handle.write("charset %s = %s;\n" % (
    #                                  part[1],
    #                                  "-".join(part[2])))
    #
    #         outfile_handle.close()
    #
    #     return 0


class Zorro ():

    def __init__(self, alignment_list, suffix="_zorro.out"):

        def zorro2rax(alignment_list):
            """ Function that converts the floating point numbers contained
            in the original zorro output files into integers that can be
            interpreted by RAxML. If multiple alignment files are provided,
            it also concatenates them in the same order """
            weigths_storage = []
            for alignment_file in alignment_list:
                # This assumes that the prefix of the
                zorro_file = alignment_file.split(".")[0] + self.suffix
                # alignment file is shared with the corresponding zorro file
                zorro_handle = open(zorro_file)
                weigths_storage += [round(float(weigth.strip())) for
                                    weigth in zorro_handle]
            return weigths_storage

        self.suffix = suffix
        self.weigth_values = zorro2rax(alignment_list)

    def write_to_file(self, output_file):
        """ Creates a concatenated file with the zorro weights for the
        corresponding alignment files """
        outfile = output_file + "_zorro.out"
        outfile_handle = open(outfile, "w")
        for weigth in self.weigth_values:
            outfile_handle.write("%s\n" % weigth)
        outfile_handle.close()


__author__ = "Diogo N. Silva"
__copyright__ = "Diogo N. Silva"
__credits__ = ["Diogo N. Silva"]
__license__ = "GPL"
__version__ = "0.1.0"
__maintainer__ = "Diogo N. Silva"
__email__ = "o.diogosilva@gmail.com"
__status__ = "Prototype"