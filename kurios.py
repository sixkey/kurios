from typing import DefaultDict, Set, List, Callable, Any, Optional, Dict, Deque, Tuple

from collections import defaultdict, deque


ComponentType = str
EntityID = int
Data = Any


class Component:
    def __init__(self, comp_type: ComponentType, data: Data):
        self.comp_type = comp_type
        self.data = data

    def __str__(self):
        return str(self.data)


class ComponentStorage:

    def __init__(self, comp_type: ComponentType):
        self.comp_type = comp_type
        self.database: DefaultDict[EntityID,
                                   List[Component]] = defaultdict(list)

    def __getitem__(self, index: EntityID) -> List[Component]:
        return self.database[index]

    def add(self, entity_id: EntityID, component: Component) -> None:

        if component.comp_type != self.comp_type:
            raise ValueError(
                f"Invalid component, this storage takes care " +
                f"of {self.comp_type}"
            )

        self.database[entity_id].append(component)

    def remove_entity(self, entity_id: EntityID) -> None:
        del self.database[entity_id]


Signature = Set[ComponentType]
AllowsSignature = Callable[[Signature], bool]


def create_min_rule(*args: Tuple[ComponentType, ...]):
    arg_set = set(args)

    def allows(signature: Signature):
        for val in arg_set:
            if val not in signature:
                return False
        return True
    return allows


def create_bl_rule(*args: Tuple[ComponentType, ...]):
    arg_set = set(args)

    def allows(signature: Signature):
        for val in signature:
            if val in arg_set:
                return False
        return True
    return allows


def create_wl_rule(*args: Tuple[ComponentType, ...]):
    arg_set = set(args)

    def allows(signature: Signature):
        for val in signature:
            if val not in arg_set:
                return False
        return True
    return allows


def build_signature_mask(allows_functions: List[AllowsSignature]):
    return SignatureMask([MaskRule(x) for x in allows_functions])


class MaskRule:

    def __init__(self, allows: AllowsSignature):
        self.allows = allows


class SignatureMask:

    def __init__(self, mask_rules: List[MaskRule]):
        self.mask_rules = mask_rules

    def contains(self, signature: Signature) -> bool:
        for rule in self.mask_rules:
            if not rule.allows(signature):
                return False
        return True


class System:
    def __init__(self, signature_mask: SignatureMask, coordinator: 'Coordinator'):
        self.signature_mask = signature_mask
        self.coordinator = coordinator

    def update(self):
        pass

    def on_entity_added(self, entity_id: EntityID) -> None:
        pass

    def on_entity_changed(self, entity_id: EntityID) -> None:
        pass

    def on_entity_removed(self, entity_id: EntityID) -> None:
        pass


class OnChangeSystem(System):

    def __init__(self, signature_mask: SignatureMask, coordinator: 'Coordinator',
                 workflow: Callable[['System', int], None]):
        System.__init__(self, signature_mask, coordinator)
        self.workflow = workflow
        self.que: Deque[EntityID] = deque()

    def update(self) -> None:

        if not self.que:
            return

        entity_id = self.que.popleft()
        while not self.signature_mask.contains(self.coordinator.get_entity_signature(entity_id)):
            if not self.que:
                return
            entity_id = self.que.popleft()

        self.workflow(self, entity_id)

    def on_entity_added(self, entity_id: EntityID) -> None:
        pass

    def on_entity_changed(self, entity_id: EntityID) -> None:

        if (self.signature_mask.contains(
                self.coordinator.get_entity_signature(entity_id))):
            self.que.append(entity_id)

    def on_entity_removed(self, entity_id: EntityID) -> None:
        return


class IDGenerator:

    def __init__(self):
        self.counter = 0
        self.dead_ids: Deque[int] = deque()

    def get(self) -> int:
        res_id = -1
        if self.dead_ids:
            res_id = self.dead_ids.popleft()
        else:
            res_id = self.counter
            self.counter += 1
        return res_id

    def add_dead(self, dead_id: int) -> None:
        self.dead_ids.append(dead_id)


def indent(string: str, spaces: int):
    return "\n".join([(spaces * " " + x) for x in string.split("\n")])


class Coordinator:

    def __init__(self):
        self.systems: List[System] = []

        self.entities: Dict[EntityID, Signature] = {}
        self.id_generator = IDGenerator()

        self.component_storages: Dict[ComponentType, ComponentStorage] = {}

    def add_entity(self) -> EntityID:
        entity_id = self.id_generator.get()
        self.entities[entity_id] = set()
        return entity_id

    def remove_entity(self, entity_id: EntityID) -> None:
        self.id_generator.add_dead(entity_id)

        for _, value in self.component_storages.items():
            value.remove_entity(entity_id)

        del self.entities[entity_id]

    def get_entity_signature(self, entity_id: EntityID) -> Signature:
        return self.entities[entity_id]

    def add_system(self, system: System):
        self.systems.append(system)

    def add_component(self, entity_id: EntityID, component: Component) -> None:

        comp_type = component.comp_type

        if comp_type not in self.component_storages:
            self.component_storages[comp_type] = ComponentStorage(comp_type)

        self.component_storages[comp_type].add(entity_id, component)

        self.entities[entity_id].add(comp_type)
        for system in self.systems:
            system.on_entity_changed(entity_id)

    def get_components(self, entity_id: EntityID, comp_type: ComponentType) -> List[Component]:
        return self.component_storages[comp_type][entity_id]

    def update(self):
        for system in self.systems:
            system.update()

    def console_draw(self):
        print("COORDINATOR:")
        print(indent("ENTITIES:", 2))
        for entity_id, signature in self.entities.items():
            print(indent(str(entity_id), 4))
            for comp_type in signature:
                print(indent(comp_type, 6))
                for component in self.get_components(entity_id, comp_type):
                    print(indent(str(component), 8))


# ------------ APPLICATION


def num_to_char(system: System, entity_id: EntityID):
    component = system.coordinator.get_components(entity_id, "number")[0]
    system.coordinator.add_component(
        entity, Component("char", str(component.data)))


def char_to_ascii(system: System, entity_id: EntityID):
    component = system.coordinator.get_components(entity_id, "char")[0]
    system.coordinator.add_component(
        entity, Component("ascii", ord(component.data)))


if __name__ == "__main__":
    coordinator = Coordinator()

    num_to_char_system = OnChangeSystem(build_signature_mask([
        create_min_rule("number"),
        create_bl_rule("char")
    ]), coordinator, num_to_char)
    coordinator.add_system(num_to_char_system)

    char_to_ascii_system = OnChangeSystem(build_signature_mask([
        create_min_rule("char"),
        create_bl_rule("ascii")
    ]), coordinator, char_to_ascii)
    coordinator.add_system(char_to_ascii_system)

    entity = coordinator.add_entity()
    coordinator.add_component(entity, Component("number", 3))

    coordinator.console_draw()
    coordinator.update()
    coordinator.console_draw()
    coordinator.update()
