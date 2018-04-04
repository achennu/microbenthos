---
title: 'MicroBenthos: a modeling framework for microbial benthic ecology'
tags:
  - marine biology
  - biogeochemistry
  - microbial ecology
  - microbial mats
  - sediments
  - modeling
  - simulation
  - microbenthic habitat

authors:
 - name: Arjun Chennu
   orcid: 0000-0002-0389-5589
   affiliation: 1
 
affiliations:
 - name: Max Planck Institute for Marine Microbiology
   index: 1
 
date: 4 April 2018
bibliography: paper.bib
---

# Summary

Microbial benthic habitats, such as microbial mats and sediments, exhibit extremely steep gradients in the physical, chemical and biotic parameters within the space of a few millimeters. These micro-environments drive the localization and exploitation of physico-chemical niches by a variety of microbial groups, such as cyanobacteria, sulfur-oxidizing bacteria, etc [@VanGemerden-1993]. Studies of biogeochemistry and microbial ecology in these systems use various sensors to profile micro-environments and infer the local budgets and productivities of the microbial groups and metabolisms [@Revsbech-1983]. Microbenthic habitats are typically modeled as diffusive-reactive systems [@deWit-1995], i.e. the dominant mass transport mode is physical diffusion of solutes within the porespaces of the sediment matrix. The “reactive” aspect refers to the presence of a large number of local sources and sinks within the mat system. 

MicroBenthos is a modeling framework to study *in silico* microbenthic habitats. The main perspective is to recognize that while modeling physical diffusion is straightforward, the larger challenge is to have a flexible way to define, compose and study various microbial metabolisms under dynamic conditions. MicroBenthos enables this by providing a high-level abstraction to compose and simulate microbenthic systems in terms of solar irradiance, chemical solutes, microbial groups and chemical or metabolic processes. While the software is written in python, with a modular structure for ease of extensibility, it can be used without programming through a (YAML) structured text file as the interface. This allows the user to focus on  specifying the constitutive relations between environmental parameters and processes as a simple mathematical formula, which is then symbolically cast (using sympy [@Meurer-2017]) into a set of coupled partial differential equations for the full model. Using a simple command, the equations can be numerically solved (using fipy [@Guyer-2009]) to study the evolution of the various model variables.

MicroBenthos provides several useful features: 

* Modular and extensible abstractions to create microbenthic systems	
* Non-programming interface to define processes and model structure
* On-line visualization of running simulations and video export
* Stateful simulations that can be interrupted and resumed
* Export of detailed model data in open archival format
* Open-source software (MIT license): https://github.com/achennu/microbenthos
* Detailed documentation and tutorials: https://microbenthos.readthedocs.io


# References
 
