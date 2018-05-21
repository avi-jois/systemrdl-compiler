from .. import component as comp
from ..node import FieldNode
from .. import rdltypes
from . import expressions
from . import type_placeholders as tp

def get_all_subclasses(cls):
        return cls.__subclasses__() + [g for s in cls.__subclasses__()
                                           for g in get_all_subclasses(s)]

class PropertyRuleBook:
    def __init__(self, compiler):
        self.compiler = compiler
        
        # Auto-discover all properties defined below and load into dict
        self.rdl_properties = {}
        for prop in get_all_subclasses(PropertyRule):
            prop_name = prop.get_name()
            if(prop.__name__.startswith("Prop_")):
                self.rdl_properties[prop_name] = prop(self.compiler)
        
        self.user_properties = {}
    
    def lookup_property(self, prop_name):
        if(prop_name in self.rdl_properties):
            return(self.rdl_properties[prop_name])
        elif(prop_name in self.user_properties):
            return(self.user_properties[prop_name])
        else:
            return(None)

#===============================================================================
# Base property
#===============================================================================
class PropertyRule:
    bindable_to = []
    valid_types = []
    default = None
    dyn_assign_allowed = True
    mutex_group = None
    
    #---------------------------------------------------------------------------
    def __init__(self, compiler):
        self.compiler = compiler
    
    #---------------------------------------------------------------------------
    @classmethod
    def get_name(cls):
        return(cls.__name__.replace("Prop_", ""))
    
    #---------------------------------------------------------------------------
    def assign_value(self, comp_def, value, err_ctx):
        """
        Used by the compiler for either local or dynamic prop assignments
        This does the following:
            - Check that the property is allowed in this component
            - Check if the value being assigned is compatible
            - Assign the property, as well as any side-effects
                subclasses extend this to define prop-specific side-effects
        """
        
        # Check if property is allowed in this component
        if(type(comp_def) not in self.bindable_to):
            self.compiler.msg.fatal(
                "The property '%s' is not valid for '%s' components" % (self.get_name(), type(comp_def).__name__.lower()),
                err_ctx
            )
        
        # unpack true type of value
        # Contents of value can be:
        #   - implied "true" assignment (bool literal, True)
        #   - precedencetype literal (instance of PrecedenceType)
        #   - user-defined enum type (subclass of UserEnum)
        #   - An expression (instance of an Expr subclass)
        if(type(value) == bool):
            assign_type = bool
        elif(type(value) == rdltypes.PrecedenceType):
            assign_type = rdltypes.PrecedenceType
        elif(issubclass(type(value), expressions.Expr)):
            assign_type = value.predict_type()
        elif(rdltypes.is_user_enum(value)):
            assign_type = rdltypes.UserEnum
        else:
            raise RuntimeError
        
        # Check if value's type is compatible
        for valid_type in self.valid_types:
            if(expressions.is_castable(assign_type, valid_type)):
                break
        else:
            self.compiler.msg.fatal(
                "Incompatible assignment to property '%s'" % self.get_name(),
                err_ctx
            )
        
        # Store the property
        comp_def.properties[self.get_name()] = value
    
    #---------------------------------------------------------------------------
    def get_default(self, node):
        """
        Used when the user queries a property, and it was not explicitly set.
        Default values are not always directly known. Sometimes they depend on
        one or more other properties.
        The base behavior will simply return the static variable's value.
        Properties with more complex rules can override this to implement
        other default value derivations
        """
        return(self.default)
    
    #---------------------------------------------------------------------------
    def validate(self, node, value):
        """
        Used during the validate phase after elaboration.
        Performs checks against the property's value
        """

#===============================================================================
class PropertyRuleBoolPair(PropertyRule):
    # Property name of the equivalent opposite
    opposite_property = ""
    
    
    def assign_value(self, comp_def, value, err_ctx):
        """
        Side effect: Ensure assignment of the opposite is cleared since it is being
        overridden
        """
        super().assign_value(comp_def, value, err_ctx)
        if(self.opposite_property in comp_def.properties):
            del comp_def.properties[self.opposite_property]
    
    def get_default(self, node):
        """
        If not explicitly set, check if the opposite was set first before returning
        default
        """
        if(self.opposite_property in node.inst.properties):
            return(not node.inst.properties[self.opposite_property])
        else:
            return(self.default)

#===============================================================================
# Placeholder for all my todos below
TODO = None

#===============================================================================
# General Properties
#===============================================================================
class Prop_name(PropertyRule):
    """
    Specifies a more descriptive name
    (5.2.1)
    """
    bindable_to = [comp.Addrmap, comp.Field, comp.Mem, comp.Reg, comp.Regfile, comp.Signal]
    valid_types = [str]
    default = ""
    dyn_assign_allowed = True
    mutex_group = None
    
    def get_default(self, node):
        """
        If name is undefined, it is presumed to be the instance name.
        (5.2.1.1)
        """
        return(node.inst.name)
    

class Prop_desc(PropertyRule):
    """
    Describes the component’s purpose.
    (5.2.1)
    """
    bindable_to = [comp.Addrmap, comp.Field, comp.Mem, comp.Reg, comp.Regfile, comp.Signal]
    valid_types = [str]
    default = None
    dyn_assign_allowed = True
    mutex_group = None

class Prop_dontcompare(PropertyRule):
    """
    Indicates the components read data shall be discarded and not compared
    against expected results.
    (5.2.2)
    """
    bindable_to = [comp.Addrmap, comp.Reg, comp.Regfile, comp.Field]
    valid_types = [bool, int]
    default = False
    dyn_assign_allowed = True
    mutex_group = "O"

class Prop_donttest(PropertyRule):
    """
    Indicates the component is not included in structural testing.
    (5.2.2)
    """
    bindable_to = [comp.Addrmap, comp.Reg, comp.Regfile, comp.Field]
    valid_types = [bool, int]
    default = False
    dyn_assign_allowed = True
    mutex_group = "O"

class Prop_ispresent(PropertyRule):
    """
    Setting ispresent to false causes the given component instance to be removed
    from the final specification.
    (5.3)
    """
    bindable_to = [comp.Addrmap, comp.Field, comp.Mem, comp.Reg, comp.Regfile, comp.Signal]
    valid_types = [bool]
    default = True
    dyn_assign_allowed = True
    mutex_group = None

class Prop_errextbus(PropertyRule):
    bindable_to = [comp.Addrmap, comp.Reg, comp.Regfile]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = False
    mutex_group = None
    
    def validate(self, node, value):
        # 10.6.1-h: errextbus is only valid for external registers
        if((node.inst.external == False) and (value == True)):
            self.compiler.msg.error(
                "The 'errextbus' property is set to 'true', but instance '%s' is not external"
                % (node.inst.inst_name),
                node.inst.inst_err_ctx
            )

class Prop_hdl_path(PropertyRule):
    bindable_to = [comp.Addrmap, comp.Reg, comp.Regfile]
    valid_types = [str]
    default = None
    dyn_assign_allowed = True
    mutex_group = None

class Prop_hdl_path_gate(PropertyRule):
    bindable_to = [comp.Addrmap, comp.Reg, comp.Regfile]
    valid_types = [str]
    default = None
    dyn_assign_allowed = True
    mutex_group = None

class Prop_hdl_path_gate_slice(PropertyRule):
    bindable_to = [comp.Addrmap, comp.Reg, comp.Regfile]
    valid_types = [tp.Array(str)]
    default = None
    dyn_assign_allowed = True
    mutex_group = None

class Prop_hdl_path_slice(PropertyRule):
    bindable_to = [comp.Addrmap, comp.Reg, comp.Regfile]
    valid_types = [tp.Array(str)]
    default = None
    dyn_assign_allowed = True
    mutex_group = None

#===============================================================================
# Signal Properties
#===============================================================================

class Prop_signalwidth(PropertyRule):
    """
    Width of the signal.
    (8.2)
    """
    bindable_to = [comp.Signal]
    valid_types = [int]
    default = None
    dyn_assign_allowed = False
    mutex_group = None
    
    def get_default(self, node):
        """
        If not explicitly set, inherits the instantiation's width
        """
        return(node.inst.width)
    
class Prop_sync(PropertyRuleBoolPair):
    """
    Signal is synchronous to the clock of the component.
    (8.2)
    """
    bindable_to = [comp.Signal]
    valid_types = [bool]
    default = True
    dyn_assign_allowed = True
    mutex_group = "N"
    
    opposite_property = "async"

class Prop_async(PropertyRuleBoolPair):
    """
    Signal is asynchronous to the clock of the component.
    (8.2)
    """
    bindable_to = [comp.Signal]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "N"
    
    opposite_property = "sync"

class Prop_cpuif_reset(PropertyRule):
    """
    Default signal to use for resetting the software interface logic. If
    cpuif_reset is not defined, this reverts to the default reset signal. This
    parameter only controls the CPU interface of a generated slave.
    (8.2)
    """
    bindable_to = [comp.Signal]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_field_reset(PropertyRule):
    """
    Default signal to use for resetting field implementations. If field_reset
    is not defined, this reverts to the default reset signal.
    (8.2)
    """
    bindable_to = [comp.Signal]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_activelow(PropertyRule):
    """
    Signal is active low (state of 0 means ON).
    (8.2)
    """
    bindable_to = [comp.Signal]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "A"

class Prop_activehigh(PropertyRule):
    """
    Signal is active high (state of 1 means ON).
    (8.2)
    """
    bindable_to = [comp.Signal]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "A"

#===============================================================================
# Field Properties
#===============================================================================

#-------------------------------------------------------------------------------
# Field access Properties
#-------------------------------------------------------------------------------
class Prop_hw(PropertyRule):
    """
    Design’s ability to sample/update a field.
    (9.4)
    """
    bindable_to = [comp.Field]
    valid_types = [rdltypes.AccessType]
    default = rdltypes.AccessType.rw
    dyn_assign_allowed = False
    mutex_group = None

class Prop_sw(PropertyRule):
    """
    Programmer’s ability to read/write a field.
    (9.4)
    """
    bindable_to = [comp.Field, comp.Mem]
    valid_types = [rdltypes.AccessType]
    default = rdltypes.AccessType.rw
    dyn_assign_allowed = True
    mutex_group = None

#-------------------------------------------------------------------------------
# Hardware Signal Properties
#-------------------------------------------------------------------------------
class Prop_next(PropertyRule):
    """
    The next value of the field; the D-input for flip-flops.
    (9.5)
    """
    bindable_to = [comp.Field]
    valid_types = [comp.Field]
    default = None
    dyn_assign_allowed = True
    mutex_group = None
    
    def validate(self, node, value):
        # 9.5.1-e: next cannot be self-referencing
        if(node.get_path() == value.get_path()):
            self.compiler.msg.error(
                "Field '%s' cannot reference itself in next property"
                % (node.inst.inst_name),
                node.inst.inst_err_ctx
            )

class Prop_reset(PropertyRule):
    """
    The reset value for the field when resetsignal is asserted.
    (9.5)
    """
    bindable_to = [comp.Field]
    valid_types = [int, comp.Field]
    default = None
    dyn_assign_allowed = True
    mutex_group = None
    
    def validate(self, node, value):
        if(type(value) == int):
            # 9.5.1-c: The reset value cannot be larger than can fit in the field
            if(value >= (2**node.inst.width)):
                self.compiler.msg.error(
                    "The reset value (%d) of field '%s' exceeds it's width (%d)"
                    % (value, node.inst.inst_name, node.inst.width),
                    node.inst.inst_err_ctx
                )
        elif(type(value) == FieldNode):
            # 9.5.1-d: When reset is a reference, it shall reference another
            # field of the same size.
            if(node.inst.width != value.inst.width):
                self.compiler.msg.error(
                    "Field '%s' references field '%s' as its reset value but they are not the same size (%d != %d)"
                    % (node.inst.inst_name, value.inst.inst_name, node.inst.width, value.inst.width),
                    node.inst.inst_err_ctx
                )
            
            # 9.5.1-e: reset cannot be self-referencing
            if(node.get_path() == value.get_path()):
                self.compiler.msg.error(
                    "Field '%s' cannot reference itself in reset property"
                    % (node.inst.inst_name),
                    node.inst.inst_err_ctx
                )
        else:
            raise RuntimeError

class Prop_resetsignal(PropertyRule):
    """
    Reference to the signal used to reset the field
    (9.5)
    """
    bindable_to = [comp.Field]
    valid_types = [comp.Signal]
    default = None
    dyn_assign_allowed = True
    mutex_group = None

#-------------------------------------------------------------------------------
# Software access properties
#-------------------------------------------------------------------------------

class Prop_rclr(PropertyRule):
    """
    Clear on read (field = 0).
    (9.6)
    """
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "P"

class Prop_rset(PropertyRule):
    """
    Set on read (field = all 1’s).
    (9.6)
    """
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "P"
    
class Prop_onread(PropertyRule):
    """
    Read side-effect.
    (9.6)
    """
    bindable_to = [comp.Field]
    valid_types = [rdltypes.OnReadType]
    default = None
    dyn_assign_allowed = True
    mutex_group = "P"
    
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Prop_woset(PropertyRule):
    """
    Write one to set (field = field | write_data).
    (9.6)
    """
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "B"

class Prop_woclr(PropertyRule):
    """
    Write one to clear (field = field & ~write_data).
    (9.6)
    """
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "B"

class Prop_onwrite(PropertyRule):
    """
    (9.6)
    """
    bindable_to = [comp.Field]
    valid_types = [rdltypes.OnWriteType]
    default = None
    dyn_assign_allowed = True
    mutex_group = "B"

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Prop_swwe(PropertyRule):
    """
    TODO: Not sure I understand the design intent of this property
    """
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "R"

class Prop_swwel(PropertyRule):
    """
    TODO: Not sure I understand the design intent of this property
    """
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "R"

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Prop_swmod(PropertyRule):
    """
    Indicates a generated output signal shall notify hardware when this field is
    modified by software
    (9.6)
    """
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_swacc(PropertyRule):
    """
    Indicates a generated output signal shall notify hardware when this field is
    accessed by software
    (9.6)
    """
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_singlepulse(PropertyRule):
    """
    Field asserts for one cycle when written 1 and then clears back to 0
    on the next cycle
    If set, field shall be instantiated with a width of 1 and the reset value
    shall be specified as 0
    (9.6)
    """
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

#-------------------------------------------------------------------------------
# Hardware access properties
#-------------------------------------------------------------------------------

class Prop_we(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "C"

class Prop_wel(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "C"

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Prop_anded(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_ored(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_xored(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Prop_fieldwidth(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [int]
    default = None
    dyn_assign_allowed = False
    mutex_group = None
    
    def get_default(self, node):
        """
        If not explicitly set, inherits the instantiation's width
        """
        return(node.inst.width)
    
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Prop_hwclr(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_hwset(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Prop_hwenable(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [comp.Field]
    default = None
    dyn_assign_allowed = True
    mutex_group = "D"

class Prop_hwmask(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [comp.Field]
    default = None
    dyn_assign_allowed = True
    mutex_group = "D"


#-------------------------------------------------------------------------------
# Counter field properties
#-------------------------------------------------------------------------------

class Prop_counter(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "E"

class Prop_threshold(PropertyRule):
    """
    alias of incrthreshold.
    """
    bindable_to = [comp.Field]
    valid_types = [bool, int, comp.Signal]
    default = False
    dyn_assign_allowed = True
    mutex_group = "incrthreshold alias"
    
    def assign_value(self, comp_def, value, err_ctx):
        """
        Set both alias and actual value
        """
        super().assign_value(comp_def, value, err_ctx)
        comp_def.properties['incrthreshold'] = value

class Prop_saturate(PropertyRule):
    """
    alias of incrsaturate.
    """
    bindable_to = [comp.Field]
    valid_types = [bool, int, comp.Signal]
    default = False
    dyn_assign_allowed = True
    mutex_group = "incrsaturate alias"
    
    def assign_value(self, comp_def, value, err_ctx):
        """
        Set both alias and actual value
        """
        super().assign_value(comp_def, value, err_ctx)
        comp_def.properties['incrsaturate'] = value

class Prop_incrthreshold(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool, int, comp.Signal]
    default = False
    dyn_assign_allowed = True
    mutex_group = "incrthreshold alias"
    
    def assign_value(self, comp_def, value, err_ctx):
        """
        Set both alias and actual value
        """
        super().assign_value(comp_def, value, err_ctx)
        comp_def.properties['incrthreshold'] = value

class Prop_incrsaturate(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool, int, comp.Signal]
    default = False
    dyn_assign_allowed = True
    mutex_group = "incrsaturate alias"
    
    def assign_value(self, comp_def, value, err_ctx):
        """
        Set both alias and actual value
        """
        super().assign_value(comp_def, value, err_ctx)
        comp_def.properties['incrsaturate'] = value

class Prop_overflow(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_underflow(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_incr(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [comp.Signal]
    default = None
    dyn_assign_allowed = True
    mutex_group = None

class Prop_incrvalue(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [int, comp.Signal]
    default = None
    dyn_assign_allowed = True
    mutex_group = "F"

class Prop_incrwidth(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [int]
    default = None
    dyn_assign_allowed = True
    mutex_group = "F"

class Prop_decrvalue(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [int, comp.Signal]
    default = None
    dyn_assign_allowed = True
    mutex_group = "G"

class Prop_decr(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [comp.Signal]
    default = None
    dyn_assign_allowed = True
    mutex_group = None

class Prop_decrwidth(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [int]
    default = None
    dyn_assign_allowed = True
    mutex_group = "G"

class Prop_decrsaturate(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool, int, comp.Signal]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

class Prop_decrthreshold(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool, int, comp.Signal]
    default = False
    dyn_assign_allowed = True
    mutex_group = None

#-------------------------------------------------------------------------------
# Field access interrupt properties
#-------------------------------------------------------------------------------

# TODO: Implement a storage location for interrupt modifiers somehow

class Prop_intr(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "E"

class Prop_enable(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [comp.Field]
    default = None
    dyn_assign_allowed = True
    mutex_group = "J"

class Prop_mask(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [comp.Field]
    default = None
    dyn_assign_allowed = True
    mutex_group = "J"

class Prop_haltenable(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [comp.Field]
    default = None
    dyn_assign_allowed = True
    mutex_group = "K"

class Prop_haltmask(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [comp.Field]
    default = None
    dyn_assign_allowed = True
    mutex_group = "K"

class Prop_sticky(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "I"

class Prop_stickybit(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "I"

#-------------------------------------------------------------------------------
# Misc properties
#-------------------------------------------------------------------------------
class Prop_encode(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [rdltypes.UserEnum]
    default = None
    dyn_assign_allowed = True
    mutex_group = None

class Prop_precedence(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [rdltypes.PrecedenceType]
    default = rdltypes.PrecedenceType.sw
    dyn_assign_allowed = True
    mutex_group = None

class Prop_paritycheck(PropertyRule):
    bindable_to = [comp.Field]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = False
    mutex_group = None

#===============================================================================
# Reg Properties
#===============================================================================

class Prop_regwidth(PropertyRule):
    """
    The bit-width of the register (power of two).
    """
    bindable_to = [comp.Reg]
    valid_types = [int]
    default = 32
    dyn_assign_allowed = False
    mutex_group = None

class Prop_accesswidth(PropertyRule):
    """
    The minimum software access width (power of two) operation that may be
    performed on the register.
    """
    bindable_to = [comp.Reg]
    valid_types = [int]
    default = None
    dyn_assign_allowed = True
    mutex_group = None
    
    def get_default(self, node):
        """
        10.6.1.d: The default value of the accesswidth property shall be
        identical to the width of the register.
        """
        return(node.get_property('regwidth'))

class Prop_shared(PropertyRule):
    bindable_to = [comp.Reg]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = False
    mutex_group = None

#===============================================================================
# Mem Properties
#===============================================================================

class Prop_mementries(PropertyRule):
    bindable_to = [comp.Mem]
    valid_types = [int]
    default = 1
    dyn_assign_allowed = False
    mutex_group = None

class Prop_memwidth(PropertyRule):
    bindable_to = [comp.Mem]
    valid_types = [int]
    default = 32
    dyn_assign_allowed = False
    mutex_group = None

#===============================================================================
# Register file properties
#===============================================================================

class Prop_alignment(PropertyRule):
    bindable_to = [comp.Addrmap, comp.Regfile]
    valid_types = [int]
    default = None
    dyn_assign_allowed = False
    mutex_group = None
    
    # RDL spec claims that if unspecified, the default alignment is based on
    # the registers width.
    # If that is taken at face-value, then it would directly conflict with the
    # 'compact' addressing rules in the situation where accesswidth < regwidth
    # Since the equivalent alignment is already handled by the addressing mode
    # rules, the alignment property's default is intentionally left as None
    # in order to distinguish it as unspecified by the user. 

class Prop_sharedextbus(PropertyRule):
    bindable_to = [comp.Addrmap, comp.Regfile]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = False
    mutex_group = None
#===============================================================================
# Address map properties
#===============================================================================

class Prop_bigendian(PropertyRule):
    bindable_to = [comp.Addrmap]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "L"

class Prop_littleendian(PropertyRule):
    bindable_to = [comp.Addrmap]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = True
    mutex_group = "L"

class Prop_addressing(PropertyRule):
    bindable_to = [comp.Addrmap]
    valid_types = [rdltypes.AddressingType]
    default = rdltypes.AddressingType.regalign
    dyn_assign_allowed = False
    mutex_group = None

class Prop_rsvdset(PropertyRule):
    """
    If true, the read value of all fields not explicitly defined is set to 1
    otherwise, it is set to 0.
    """
    bindable_to = [comp.Addrmap]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = False
    mutex_group = "Q"

class Prop_rsvdsetX(PropertyRule):
    bindable_to = [comp.Addrmap]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = False
    mutex_group = "Q"

class Prop_msb0(PropertyRuleBoolPair):
    bindable_to = [comp.Addrmap]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = False
    mutex_group = "M"
    
    opposite_property = "lsb0"
    
class Prop_lsb0(PropertyRuleBoolPair):
    bindable_to = [comp.Addrmap]
    valid_types = [bool]
    default = True
    dyn_assign_allowed = False
    mutex_group = "M"
    
    opposite_property = "msb0"
    
#-------------------------------------------------------------------------------
class Prop_bridge(PropertyRule):
    bindable_to = [comp.Addrmap]
    valid_types = [bool]
    default = False
    dyn_assign_allowed = False
    mutex_group = None
